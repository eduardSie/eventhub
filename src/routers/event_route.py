import uuid
import logging
import os
import boto3
from botocore.client import Config
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.event import Event
from src.schemas.event_schema import EventOut

# --- S3 CONFIG (той самий) ---
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Events"])
ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_FILE_SIZE_MB = 20

S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_REGION = os.getenv("S3_REGION", "eu-central-1")
S3_PUBLIC_BASE = os.getenv("S3_PUBLIC_BASE", "")

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name=S3_REGION,
    )

def s3_key_for_filename(filename: str) -> str:
    return f"uploads/{filename}"

def make_presigned_url(key: str, expires_in: int = 3600) -> str:
    if not key: return None
    if key.startswith("http"): return key
    if S3_PUBLIC_BASE:
        return f"{S3_PUBLIC_BASE.rstrip('/')}/{key.lstrip('/')}"
    try:
        s3 = get_s3_client()
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key.lstrip("/")},
            ExpiresIn=expires_in,
        )
    except Exception as e:
        logger.error(f"S3 presign error: {e}")
        return key

# --- ROUTES ---

@router.get("/events", response_model=list[EventOut])
async def list_events(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event))
    events = result.scalars().all()
    for ev in events:
        ev.image_url = make_presigned_url(ev.image_url)
    return events

@router.get("/event/{event_id}", response_model=EventOut)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.image_url = make_presigned_url(event.image_url)
    return event

@router.post("/event", response_model=EventOut, status_code=201)
async def create_event(
        title: str = Form(...),
        organizer_id: int = Form(...),
        date_start: datetime = Form(...),
        price: Decimal = Form(0.00),
        
        city_id: Optional[int] = Form(None),
        description: Optional[str] = Form(None),
        website_url: Optional[str] = Form(None),
        date_end: Optional[datetime] = Form(None),
        registration_deadline: Optional[datetime] = Form(None),
        location_address: Optional[str] = Form(None),
        is_online: bool = Form(False),
        
        image: UploadFile = File(None),
        db: AsyncSession = Depends(get_db),
):
    event = Event(
        title=title,
        organizer_id=organizer_id,
        date_start=date_start,
        price=price,
        city_id=city_id,
        description=description,
        website_url=website_url,
        date_end=date_end,
        registration_deadline=registration_deadline,
        location_address=location_address,
        is_online=is_online
    )

    s3_uploaded_key = None
    if image:
        if image.content_type not in ALLOWED:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        
        ext = ALLOWED[image.content_type]
        filename = f"{uuid.uuid4()}.{ext}"
        key = s3_key_for_filename(filename)
        
        try:
            s3 = get_s3_client()
            s3.upload_fileobj(
                Fileobj=image.file,
                Bucket=S3_BUCKET,
                Key=key,
                ExtraArgs={"ContentType": image.content_type, "ACL": "public-read"}
            )
            s3_uploaded_key = key
            event.image_url = key
        except Exception as e:
            logger.error("Upload failed", exc_info=e)
            raise HTTPException(status_code=500, detail="Image upload failed")

    db.add(event)
    try:
        await db.commit()
        await db.refresh(event)
    except Exception as e:
        logger.error("DB Error", exc_info=e)
        if "foreign key constraint" in str(e).lower():
             raise HTTPException(status_code=400, detail="Invalid organizer_id or city_id provided.")
        
        if s3_uploaded_key:
            try:
                get_s3_client().delete_object(Bucket=S3_BUCKET, Key=s3_uploaded_key)
            except: pass
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    event.image_url = make_presigned_url(event.image_url)
    return event

@router.delete("/event/{event_id}", status_code=204)
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Not found")
    
    if event.image_url:
        try:
            get_s3_client().delete_object(Bucket=S3_BUCKET, Key=event.image_url)
        except: pass

    await db.delete(event)
    await db.commit()
    return None