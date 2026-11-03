
from io import BytesIO
from uuid import uuid4
from app.profiling import profile_dataframe
from app.quality import check_data_quality

from fastapi import Body
from fastapi.responses import StreamingResponse

from app.cleaning import clean_dataframe
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(
    title="DataLens API",
    description="AI-powered Data Quality and Analytics Copilot",
    version="0.2.0",
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@app.get("/")
def home():
    return {
        "message": "Welcome to DataLens API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/api/v1/datasets/upload")
async def upload_csv(file: UploadFile = File(...)):
    # 1. Validate the filename
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Only CSV files are supported.",
        )

    # 2. Read the uploaded file, with a size limit
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

    # 3. Parse the CSV using Pandas
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

    # 4. Validate the parsed dataset
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

    # 5. Prepare a small preview as JSON
    preview = df.head(5).to_json(
        orient="records",
        date_format="iso",
    )

    import json
    preview_rows = json.loads(preview)

    profile = profile_dataframe(df)

    quality_report = check_data_quality(
        df,
        non_negative_columns=["customer_age", "quantity"],
    )

    return {
        "filename": file.filename,
        "status": "success",
        "profile": profile,
        "quality_report": quality_report,
    }
