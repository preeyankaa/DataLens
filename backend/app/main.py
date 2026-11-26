import json
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from typing import Optional, List, Dict, Any

import pandas as pd
from pydantic import BaseModel, Field
from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from app.profiling import profile_dataframe
from app.quality import check_data_quality
from app.cleaning import clean_dataframe
from app.file_loader import load_dataframe, LoadError, SUPPORTED_EXTENSIONS
from app.ai_service import ask_groq, generate_dashboard_insights
from app.data_analysis import (
    build_dataset_context,
    run_query,
    explain_change,
)
from app.trust import build_cleaning_report
from app.codegen import generate_cleaning_code
from app.exporter import build_csv_bytes, build_excel_bytes
from app.report_pdf import build_pdf_report
from app.dashboard_builder import build_dashboard_data
from app.visualization import (
    build_visualization_data,
    build_custom_chart,
)


# --------------------------------------------------
# 1. Request models
# --------------------------------------------------

class QuestionRequest(BaseModel):
    question: str
    version: str = "cleaned"
    history: List[Dict[str, str]] = Field(default_factory=list)


class CustomChartRequest(BaseModel):
    chart_type: str
    x_column: str
    y_column: Optional[str] = None
    aggregation: str = "sum"
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    top_n: int = 10


# --------------------------------------------------
# 2. FastAPI application
# --------------------------------------------------

app = FastAPI(
    title="DataLens API",
    description="AI-powered Data Quality and Analytics Copilot",
    version="0.4.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# --------------------------------------------------
# 3. Configuration, temporary storage and caches
# --------------------------------------------------

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

NON_NEGATIVE_COLUMNS = ["customer_age", "quantity"]

SAMPLE_FILENAME = "datalens_sample_sales.csv"
SAMPLE_PATH = Path(__file__).resolve().parent / "sample_data" / SAMPLE_FILENAME

# Store original uploaded datasets
datasets = {}

# Store cleaned versions separately
cleaned_datasets = {}

# Cleaning reconciliation reports (what changed, before/after totals)
cleaning_reports = {}

# Original file names (used in the exported Python script)
dataset_files = {}

# Caches so repeated questions and page loads are fast
context_cache = {}     # (dataset_id, "original"|"cleaned") -> AI summary JSON
dashboard_cache = {}   # (dataset_id, using_cleaned, roles_json) -> dashboard


def invalidate_caches(dataset_id: str):
    """Forget cached results for a dataset (call after its data changes)."""
    for cache in (context_cache, dashboard_cache):
        for key in [k for k in cache if k[0] == dataset_id]:
            del cache[key]


def get_df(dataset_id: str, version: str = "cleaned"):
    """
    Return (dataframe, using_cleaned).
    'cleaned' quietly falls back to the uploaded data if cleaning has
    not been applied yet.
    """
    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    if version not in ("original", "cleaned"):
        raise HTTPException(
            status_code=400,
            detail="Version must be 'original' or 'cleaned'.",
        )

    if version == "cleaned" and dataset_id in cleaned_datasets:
        return cleaned_datasets[dataset_id], True

    return datasets[dataset_id], False


def parse_roles(raw: Optional[str]) -> Dict[str, Optional[str]]:
    """Parse the column choices sent by the Confirm columns panel."""
    if not raw:
        return {}

    try:
        value = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid roles value.")

    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Roles must be an object.")

    return {
        str(key): (str(item) if item else None)
        for key, item in value.items()
    }


# --------------------------------------------------
# 4. Home and health-check endpoints
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Welcome to DataLens API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }


# --------------------------------------------------
# 5. Upload endpoints (CSV, Excel and the built-in sample)
# --------------------------------------------------

def register_dataset(df, filename, load_info):
    """Store a loaded dataset and build its first report."""

    # Generate a unique dataset ID
    dataset_id = str(uuid4())

    # Store a copy of the uploaded dataset
    datasets[dataset_id] = df.copy(deep=True)
    dataset_files[dataset_id] = filename

    # Generate dataset profile
    profile = profile_dataframe(df)

    # Run data quality checks
    quality_report = check_data_quality(
        df,
        non_negative_columns=NON_NEGATIVE_COLUMNS,
    )

    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "status": "success",
        "load_info": load_info,
        "profile": profile,
        "quality_report": quality_report,
    }


@app.post("/api/v1/datasets/upload")
async def upload_file(file: UploadFile = File(...)):

    filename = file.filename or ""

    # Validate filename
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=415,
            detail="Please upload a CSV or Excel (.xlsx) file.",
        )

    try:
        # Read uploaded file with size limit
        contents = await file.read(MAX_FILE_SIZE + 1)
    finally:
        await file.close()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 10 MB.",
        )

    # Parsing and profiling are CPU work, so run them off the event loop
    try:
        df, load_info = await run_in_threadpool(
            load_dataframe, contents, filename
        )
    except LoadError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return await run_in_threadpool(
        register_dataset, df, filename, load_info
    )


@app.post("/api/v1/datasets/sample")
def load_sample_dataset():
    """Load the bundled, deliberately messy demo dataset."""

    if not SAMPLE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Sample dataset is not installed on the server.",
        )

    try:
        df, load_info = load_dataframe(SAMPLE_PATH.read_bytes(), SAMPLE_FILENAME)
    except LoadError as error:
        raise HTTPException(status_code=500, detail=str(error))

    load_info["notes"] = [
        "This is demo data with missing values, duplicates, mixed date "
        "formats and inconsistent spellings added on purpose.",
        *load_info.get("notes", []),
    ]

    return register_dataset(df, SAMPLE_FILENAME, load_info)


# --------------------------------------------------
# 6. Clean dataset preview endpoint
# --------------------------------------------------

@app.post("/api/v1/datasets/{dataset_id}/clean/preview")
def preview_cleaning(
    dataset_id: str,
    operations: dict = Body(...),
):

    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    original_df = datasets[dataset_id]

    try:
        cleaned_df, changes = clean_dataframe(
            original_df,
            operations,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    except (TypeError, KeyError) as error:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid cleaning configuration: {error}",
        )

    before = {
        "rows": len(original_df),
        "columns": len(original_df.columns),
        "missing_values": int(original_df.isna().sum().sum()),
        "duplicate_rows": int(original_df.duplicated().sum()),
    }

    after = {
        "rows": len(cleaned_df),
        "columns": len(cleaned_df.columns),
        "missing_values": int(cleaned_df.isna().sum().sum()),
        "duplicate_rows": int(cleaned_df.duplicated().sum()),
    }

    preview_json = cleaned_df.head(5).to_json(
        orient="records",
        date_format="iso",
    )

    preview_rows = json.loads(preview_json)

    return {
        "dataset_id": dataset_id,
        "status": "success",
        "before": before,
        "after": after,
        "changes": changes,
        "preview": preview_rows,
    }


# --------------------------------------------------
# 7. Apply cleaning and save cleaned dataset
# --------------------------------------------------

@app.post("/api/v1/datasets/{dataset_id}/clean/apply")
def apply_cleaning(
    dataset_id: str,
    operations: dict = Body(...),
):

    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    original_df = datasets[dataset_id]

    try:
        cleaned_df, changes = clean_dataframe(
            original_df,
            operations,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    except (TypeError, KeyError) as error:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid cleaning configuration: {error}",
        )

    # Save cleaned version separately
    cleaned_datasets[dataset_id] = cleaned_df.copy(deep=True)

    # Keep a verifiable record of what cleaning did
    try:
        cleaning_reports[dataset_id] = build_cleaning_report(
            original_df, cleaned_df, changes, operations
        )
    except Exception as error:
        print(f"Cleaning report error: {error}")
        cleaning_reports.pop(dataset_id, None)

    # Cleaned data changed, so old summaries and dashboards are stale
    invalidate_caches(dataset_id)

    return {
        "dataset_id": dataset_id,
        "status": "success",
        "message": "Cleaning applied successfully.",
        "before": {
            "rows": len(original_df),
            "columns": len(original_df.columns),
            "missing_values": int(original_df.isna().sum().sum()),
            "duplicate_rows": int(original_df.duplicated().sum()),
        },
        "after": {
            "rows": len(cleaned_df),
            "columns": len(cleaned_df.columns),
            "missing_values": int(cleaned_df.isna().sum().sum()),
            "duplicate_rows": int(cleaned_df.duplicated().sum()),
        },
        "changes": changes,
    }


# --------------------------------------------------
# 8. Retrieve original or cleaned dataset
# --------------------------------------------------

@app.get("/api/v1/datasets/{dataset_id}/versions/{version}")
def get_dataset_version(
    dataset_id: str,
    version: str,
):

    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    if version == "original":
        df = datasets[dataset_id]

    elif version == "cleaned":
        if dataset_id not in cleaned_datasets:
            raise HTTPException(
                status_code=404,
                detail="Cleaned dataset not available. Apply cleaning first.",
            )

        df = cleaned_datasets[dataset_id]

    else:
        raise HTTPException(
            status_code=400,
            detail="Version must be 'original' or 'cleaned'.",
        )

    statistics = {
        "rows": len(df),
        "columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
    }

    preview = json.loads(
        df.head(5).to_json(
            orient="records",
            date_format="iso",
        )
    )

    return {
        "dataset_id": dataset_id,
        "version": version,
        "status": "success",
        "statistics": statistics,
        "column_names": df.columns.tolist(),
        "preview": preview,
    }


# --------------------------------------------------
# 9. Download cleaned CSV endpoint
# --------------------------------------------------

@app.post("/api/v1/datasets/{dataset_id}/clean/download")
def download_cleaned_csv(
    dataset_id: str,
    operations: dict = Body(...),
):

    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    original_df = datasets[dataset_id]

    try:
        cleaned_df, changes = clean_dataframe(
            original_df,
            operations,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    except (TypeError, KeyError) as error:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid cleaning configuration: {error}",
        )

    csv_buffer = BytesIO(
        cleaned_df.to_csv(index=False).encode("utf-8-sig")
    )

    return StreamingResponse(
        csv_buffer,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="datalens_cleaned.csv"',
            "X-Cleaned-Rows": str(len(cleaned_df)),
            "X-Original-Rows": str(len(original_df)),
        },
    )


# --------------------------------------------------
# 10. Cleaning report, Python export and reset
# --------------------------------------------------

@app.get("/api/v1/datasets/{dataset_id}/clean/report")
def get_cleaning_report(dataset_id: str):

    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    report = cleaning_reports.get(dataset_id)

    if report is None:
        return {"available": False}

    return {"available": True, **report}


@app.post("/api/v1/datasets/{dataset_id}/clean/code")
def export_cleaning_code(
    dataset_id: str,
    operations: dict = Body(...),
):
    """Python (pandas) script that repeats the chosen cleaning steps."""

    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    try:
        code = generate_cleaning_code(
            datasets[dataset_id],
            operations,
            source_name=dataset_files.get(dataset_id, "your_file.csv"),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    return {"code": code}


@app.delete("/api/v1/datasets/{dataset_id}/clean")
def reset_cleaning(dataset_id: str):
    """Undo an applied cleaning. The uploaded original is never touched."""

    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    cleaned_datasets.pop(dataset_id, None)
    cleaning_reports.pop(dataset_id, None)
    invalidate_caches(dataset_id)

    return {"status": "success", "message": "Cleaning removed. Using the original data."}


# --------------------------------------------------
# 11. Ask questions about dataset
# --------------------------------------------------
# Plain `def` (not async) so FastAPI runs the pandas work and the AI call
# in a worker thread and other requests are not blocked.

@app.post("/api/v1/datasets/{dataset_id}/ask")
def ask_dataset_question(
    dataset_id: str,
    request: QuestionRequest,
):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    df, using_cleaned = get_df(dataset_id, request.version)
    used_version = "cleaned" if using_cleaned else "original"

    # The dataset summary is built once, then reused for every question
    cache_key = (dataset_id, used_version)
    context = context_cache.get(cache_key)

    if context is None:
        context = build_dataset_context(df)
        context_cache[cache_key] = context

    def run_tool(name, arguments):
        if name == "run_query":
            return run_query(df, arguments)
        if name == "explain_change":
            return explain_change(df, arguments)
        return {"error": f"Unknown tool '{name}'."}

    try:
        result = ask_groq(
            question=question,
            context=context,
            history=request.history,
            tool_runner=run_tool,
        )

        return {
            "dataset_id": dataset_id,
            "version": used_version,
            "requested_version": request.version,
            "question": question,
            "answer": result["answer"],
            "calculations": result["calculations"],
            "status": "success",
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to answer question: {str(error)}",
        )


# --------------------------------------------------
# 12. Dataset visualization endpoint
# --------------------------------------------------

@app.get("/api/v1/datasets/{dataset_id}/charts")
def get_dataset_charts(
    dataset_id: str,
    version: str = "cleaned",
):

    df, using_cleaned = get_df(dataset_id, version)

    try:
        result = build_visualization_data(df)

        return {
            "dataset_id": dataset_id,
            "version": "cleaned" if using_cleaned else "original",
            **result,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate charts: {str(error)}",
        )


# --------------------------------------------------
# 13. AI Dashboard endpoint
# --------------------------------------------------
# roles    JSON of column choices from the "Confirm columns" panel
# refresh  true = ignore the cache and rebuild

def compute_dashboard(dataset_id, version, role_overrides, refresh=False):
    """Build (or fetch from cache) the dashboard payload. Shared with the PDF."""

    df, using_cleaned = get_df(dataset_id, version)

    cache_key = (
        dataset_id,
        using_cleaned,
        json.dumps(role_overrides, sort_keys=True),
    )

    if not refresh and cache_key in dashboard_cache:
        return dashboard_cache[cache_key]

    try:
        visualization = build_dashboard_data(df, role_overrides)

        try:
            dashboard_ai = generate_dashboard_insights(
                charts=visualization["charts"],
                summary=visualization["summary"],
                version="cleaned" if using_cleaned else "original",
            )
        except Exception:
            dashboard_ai = None  # dashboard still works without AI

        payload = {
            "dataset_id": dataset_id,
            "version": "cleaned" if using_cleaned else "original",
            "using_cleaned": using_cleaned,
            **visualization,
            "dashboard_ai": dashboard_ai,
        }

        dashboard_cache[cache_key] = payload
        return payload

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate AI dashboard: {str(error)}",
        )


@app.get("/api/v1/datasets/{dataset_id}/dashboard")
def get_ai_dashboard(
    dataset_id: str,
    version: str = "cleaned",
    roles: Optional[str] = None,
    refresh: bool = False,
):
    return compute_dashboard(
        dataset_id, version, parse_roles(roles), refresh
    )


# --------------------------------------------------
# 14. Custom interactive chart endpoint
# --------------------------------------------------

@app.post("/api/v1/datasets/{dataset_id}/charts/custom")
def create_custom_chart(
    dataset_id: str,
    request: CustomChartRequest,
    version: str = "cleaned",
):

    df, _ = get_df(dataset_id, version)

    try:
        chart = build_custom_chart(
            df=df,
            chart_type=request.chart_type,
            x_column=request.x_column,
            y_column=request.y_column,
            aggregation=request.aggregation,
            filters=request.filters,
            top_n=request.top_n,
        )

        return {
            "success": True,
            "dataset_id": dataset_id,
            "version": version,
            "chart": chart,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not generate chart: {str(error)}",
        )


# --------------------------------------------------
# 15. Export cleaned data and the PDF report
# --------------------------------------------------

def safe_file_stem(name):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name or "dataset").stem)
    return stem.strip("._")[:60] or "dataset"


def quality_scores(dataset_id):
    """Data quality before cleaning and (if cleaned) after."""

    before = check_data_quality(
        datasets[dataset_id], non_negative_columns=NON_NEGATIVE_COLUMNS
    )
    after = None

    if dataset_id in cleaned_datasets:
        after = check_data_quality(
            cleaned_datasets[dataset_id],
            non_negative_columns=NON_NEGATIVE_COLUMNS,
        )

    return before, after


@app.get("/api/v1/datasets/{dataset_id}/export")
def export_dataset(
    dataset_id: str,
    file_format: str = Query("xlsx", alias="format"),
    version: str = "cleaned",
):
    """Download the cleaned data as Excel (with a change log) or CSV."""

    df, using_cleaned = get_df(dataset_id, version)

    if file_format not in ("xlsx", "csv"):
        raise HTTPException(
            status_code=400,
            detail="Format must be 'xlsx' or 'csv'.",
        )

    source = dataset_files.get(dataset_id, "dataset")
    stem = safe_file_stem(source)
    label = "cleaned" if using_cleaned else "original"

    if file_format == "csv":
        content = build_csv_bytes(df)
        media_type = "text/csv; charset=utf-8"
    else:
        report = cleaning_reports.get(dataset_id) if using_cleaned else None
        before, after = quality_scores(dataset_id) if report else (None, None)

        content = build_excel_bytes(
            df,
            source,
            using_cleaned,
            report=report,
            quality_before=before["quality_score"] if before else None,
            quality_after=after["quality_score"] if after else None,
        )
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{stem}-{label}.{file_format}"'
        },
    )


@app.get("/api/v1/datasets/{dataset_id}/report/pdf")
def download_pdf_report(
    dataset_id: str,
    roles: Optional[str] = None,
):
    """PDF with the cleaning report, KPIs, insights and every chart."""

    dashboard = compute_dashboard(
        dataset_id, "cleaned", parse_roles(roles)
    )
    before, after = quality_scores(dataset_id)

    try:
        pdf = build_pdf_report({
            "filename": dataset_files.get(dataset_id, "dataset"),
            "using_cleaned": dashboard["using_cleaned"],
            "dashboard": dashboard,
            "cleaning_report": cleaning_reports.get(dataset_id),
            "quality_before": before,
            "quality_after": after,
        })
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to create the report: {str(error)}",
        )

    stem = safe_file_stem(dataset_files.get(dataset_id, "dataset"))

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}-datalens-report.pdf"'
        },
    )