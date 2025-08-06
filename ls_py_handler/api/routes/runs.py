import asyncio
from io import BytesIO
import uuid
from typing import Any, Dict, List, Optional

import asyncpg
import orjson
from aiobotocore.session import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4, BaseModel, Field

from ls_py_handler.config.settings import settings

router = APIRouter(prefix="/runs", tags=["runs"])


class Run(BaseModel):
    id: Optional[UUID4] = Field(default_factory=uuid.uuid4)
    trace_id: UUID4
    name: str
    inputs: Dict[str, Any] = {}
    outputs: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}


async def get_db_conn():
    """Get a database connection."""
    conn = await asyncpg.connect(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    try:
        yield conn
    finally:
        await conn.close()


async def get_s3_client():
    """Get an S3 client for MinIO."""
    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    ) as client:
        yield client


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_runs(
    runs: List[Run],
    db: asyncpg.Connection = Depends(get_db_conn),
    s3: Any = Depends(get_s3_client),
):
    """
    Create new runs in batch.

    Takes a JSON array of Run objects, 
    Serialize each Run object as bytes delimited by newline,
    Uploads them as single object to MinIO in NDJSON S3 bucket,
    Stores start and end offset of each Run object bytes in PostgreSQL.
    """
    if not runs:
        raise HTTPException(status_code=400, detail="No runs provided")

    # Prepare the batch for S3 upload
    batch_id = str(uuid.uuid4())
    bucket = settings.S3_BUCKET_NAME
    key = f"batches/{batch_id}.ndjson"

    buf = BytesIO()
    records = []
    offset = 0
    run_ids = []

    # Serialize each run as a line in NDJSON, track byte offsets
    for run in runs:
        data = orjson.dumps(run.model_dump())
        buf.write(data + b"\n")
        start = offset
        end = offset + len(data)
        run_ids.append(run.id)
        records.append((run.id, run.trace_id, run.name, bucket, key, start, end))
        offset = end + 1  # account for the newline

    buf.seek(0)
    # Single PUT of the whole NDJSON blob
    await s3.put_object(Bucket=bucket, Key=key, Body=buf)

    # Batch insert via COPY (or executemany)
    await db.copy_records_to_table(
        'runs',
        records=records,
        columns=['id', 'trace_id', 'name', 's3_bucket', 's3_key', 'start_offset', 'end_offset'],
    )

    return {"status": "created", "run_ids": run_ids}


@router.get("/{run_id}", status_code=status.HTTP_200_OK)
async def get_run(
    run_id: UUID4,
    db: asyncpg.Connection = Depends(get_db_conn),
    s3: Any = Depends(get_s3_client),
):
    """
    Get a run by its ID.
    """

    row = await db.fetchrow(
        "SELECT s3_bucket, s3_key, start_offset, end_offset FROM runs WHERE id=$1",
        run_id,
    )
    byte_range = f"bytes={row['start_offset']}-{row['end_offset']}"
    resp = await s3.get_object(Bucket=row['s3_bucket'], Key=row['s3_key'], Range=byte_range)
    body = await resp['Body'].read()
    run = orjson.loads(body)
    return run
