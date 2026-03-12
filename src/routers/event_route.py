import uuid
import logging
import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.auth import get_current_user, require_admin
from src.helpers import s3
from src.models.event import Event
from src.models.tag import EventTag
from src.models.audit_log import EventAuditLog
from src.models.user import User
from src.schemas.event_schema import EventOut, EventUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Events"])


def _resolve_tags(events):
    """Populate .tags and presign .image_url on event instance(s)."""
    for ev in events if isinstance(events, list) else [events]:
        ev.tags = [et.tag for et in ev.event_tags]
        ev.image_url = s3.presign(ev.image_url)
    return events


# ─── PUBLIC ROUTES ────────────────────────────────────────────────

@router.get("/events", response_model=List[EventOut])
async def list_events(
    search: Optional[str] = Query(None, description="Filter by title/description"),
    city_id: Optional[int] = Query(None),
    organizer_id: Optional[int] = Query(None),
    is_online: Optional[bool] = Query(None),
    tag_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Public: View Event List with optional Search & Filter."""
    query = select(Event).options(
        selectinload(Event.event_tags).selectinload(EventTag.tag)
    )
    if search:
        query = query.where(
            Event.title.ilike(f"%{search}%") | Event.description.ilike(f"%{search}%")
        )
    if city_id is not None:
        query = query.where(Event.city_id == city_id)
    if organizer_id is not None:
        query = query.where(Event.organizer_id == organizer_id)
    if is_online is not None:
        query = query.where(Event.is_online == is_online)
    if tag_id is not None:
        query = query.join(EventTag, Event.id == EventTag.event_id).where(EventTag.tag_id == tag_id)

    result = await db.execute(query)
    events = result.scalars().all()
    _resolve_tags(list(events))
    return events


@router.get("/event/{event_id}", response_model=EventOut)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Public: View Event Details."""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _resolve_tags(event)
    return event


# ─── ADMIN ROUTES ─────────────────────────────────────────────────

@router.post("/event", response_model=EventOut, status_code=201)
async def create_event(
    title: str = Form(...),
    organizer_id: int = Form(...),
    date_start: datetime = Form(...),
    price: Decimal = Form(Decimal("0.00")),
    city_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    date_end: Optional[datetime] = Form(None),
    registration_deadline: Optional[datetime] = Form(None),
    location_address: Optional[str] = Form(None),
    is_online: bool = Form(False),
    tag_ids: Optional[str] = Form(None, description="Comma-separated tag IDs, e.g. '1,2,3'"),
    image: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: Create Event."""
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
        is_online=is_online,
    )

    s3_uploaded_key = None
    if image:
        if image.content_type not in s3.ALLOWED_IMG:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        ext = s3.ALLOWED_IMG[image.content_type]
        key = f"uploads/{uuid.uuid4()}.{ext}"
        try:
            contents = await image.read()
            s3.upload_fileobj(io.BytesIO(contents), key, image.content_type)
            s3_uploaded_key = key
            event.image_url = key
        except Exception as e:
            logger.error("Upload failed", exc_info=e)
            raise HTTPException(status_code=500, detail="Image upload failed")

    db.add(event)
    try:
        await db.flush()
        if tag_ids:
            parsed_ids = [int(t.strip()) for t in tag_ids.split(",") if t.strip().isdigit()]
            for tid in parsed_ids:
                db.add(EventTag(event_id=event.id, tag_id=tid))
        await db.commit()
    except Exception as e:
        logger.error("DB Error", exc_info=e)
        if s3_uploaded_key:
            s3.delete_object(s3_uploaded_key)
        if "foreign key" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid organizer_id, city_id, or tag_id.")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    result = await db.execute(
        select(Event)
        .where(Event.id == event.id)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
    )
    event = result.scalar_one()
    _resolve_tags(event)
    return event


@router.patch("/event/{event_id}", response_model=EventOut)
async def update_event(
    event_id: int,
    payload: EventUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: Edit Event (with audit log)."""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = payload.model_dump(exclude_unset=True, exclude={"tag_ids"})
    for field, new_val in update_data.items():
        old_val = getattr(event, field, None)
        if str(old_val) != str(new_val):
            db.add(EventAuditLog(
                event_id=event_id,
                changed_by=admin.id,
                changed_column=field,
                old_value=str(old_val),
                new_value=str(new_val),
            ))
        setattr(event, field, new_val)

    if payload.tag_ids is not None:
        await db.execute(
            EventTag.__table__.delete().where(EventTag.event_id == event_id)
        )
        for tid in payload.tag_ids:
            db.add(EventTag(event_id=event_id, tag_id=tid))

    event.updated_at = datetime.now(timezone.utc)
    await db.commit()

    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
    )
    event = result.scalar_one()
    _resolve_tags(event)
    return event


@router.delete("/event/{event_id}", status_code=204)
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: Delete Event."""
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Not found")
    s3.delete_object(event.image_url)
    await db.delete(event)
    await db.commit()
    return None