
import json
from io import BytesIO
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, Body
from fastapi.responses import StreamingResponse

from app.profiling import profile_dataframe
from app.quality import check_data_quality
from app.cleaning import clean_dataframe

from fastapi.middleware.cors import CORSMiddleware

# --------------------------------------------------
# 1. FastAPI application
# --------------------------------------------------

app = FastAPI(
    title="DataLens API",
    description="AI-powered Data Quality and Analytics Copilot",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# 2. Configuration and temporary storage
# --------------------------------------------------

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Temporary in-memory storage for uploaded datasets.
# Each dataset is stored using a unique ID.
datasets = {}


# --------------------------------------------------
# 3. Home and health-check endpoints
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
# 4. Upload CSV endpoint
# --------------------------------------------------

@app.post("/api/v1/datasets/upload")
async def upload_csv(file: UploadFile = File(...)):

    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Only CSV files are supported.",
        )

    try:
        # Read uploaded file with size limit
        contents = await file.read(MAX_FILE_SIZE + 1)

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

        # Parse CSV using Pandas
        try:
            df = pd.read_csv(BytesIO(contents))
        except pd.errors.EmptyDataError:
            raise HTTPException(
                status_code=400,
                detail="The CSV does not contain readable data or headers.",
            )
        except (pd.errors.ParserError, UnicodeDecodeError):
            raise HTTPException(
                status_code=400,
                detail="Unable to parse the CSV. Check its encoding and format.",
            )

    finally:
        await file.close()

    # Validate columns
    if len(df.columns) == 0:
        raise HTTPException(
            status_code=400,
            detail="The CSV does not contain any columns.",
        )

    if any(not isinstance(col, str) or not col.strip() for col in df.columns):
        raise HTTPException(
            status_code=400,
            detail="Column names must not be empty.",
        )

    # Generate a unique dataset ID
    dataset_id = str(uuid4())

    # Store a copy of the uploaded dataset
    datasets[dataset_id] = df.copy(deep=True)

    # Generate dataset profile
    profile = profile_dataframe(df)

    # Run data quality checks
    quality_report = check_data_quality(
        df,
        non_negative_columns=["customer_age", "quantity"],
    )

    return {
        "dataset_id": dataset_id,
        "filename": file.filename,
        "status": "success",
        "profile": profile,
        "quality_report": quality_report,
    }


# --------------------------------------------------
# 5. Clean dataset preview endpoint
# --------------------------------------------------

@app.post("/api/v1/datasets/{dataset_id}/clean/preview")
def preview_cleaning(
    dataset_id: str,
    operations: dict = Body(...),
):

    # Check whether dataset exists
    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    # Get original dataset
    original_df = datasets[dataset_id]

    try:
        # Clean a copy of the original dataset
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

    # Calculate before and after statistics
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

    # Generate preview
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
# 6. Download cleaned CSV endpoint
# --------------------------------------------------

@app.post("/api/v1/datasets/{dataset_id}/clean/download")
def download_cleaned_csv(
    dataset_id: str,
    operations: dict = Body(...),
):

    # Check whether dataset exists
    if dataset_id not in datasets:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please upload the CSV again.",
        )

    # Get original dataset
    original_df = datasets[dataset_id]

    try:
        # Apply the same cleaning operations
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

    # Convert cleaned DataFrame into CSV bytes
    csv_buffer = BytesIO(
        cleaned_df.to_csv(index=False).encode("utf-8-sig")
    )

    # Return downloadable CSV file
    return StreamingResponse(
        csv_buffer,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="datalens_cleaned.csv"',
            "X-Cleaned-Rows": str(len(cleaned_df)),
            "X-Original-Rows": str(len(original_df)),
        },
    )
