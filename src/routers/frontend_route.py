"""
Frontend router — serves Jinja2 HTML pages.
Auth is stored in an HttpOnly cookie (JWT token).
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Query, Request, Response, UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth import create_access_token, hash_password, verify_password
from src.core.database import get_db
from src.helpers import s3
from src.models.audit_log import EventAuditLog
from src.models.bookmark import Bookmark
from src.models.city import City
from src.models.country import Country
from src.models.event import Event
from src.models.organizer import Organizer
from src.models.tag import EventTag, Tag
from src.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)

# ── Templates ──────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(__file__))  # src/
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ── JWT settings ───────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM  = "HS256"
COOKIE_KEY = "access_token"


# ── Validation helpers ─────────────────────────────────────────────
def _strip(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    return v if v else None


def _require(value: Optional[str], label: str) -> str:
    v = _strip(value)
    if not v:
        raise ValueError(f"«{label}» is required and cannot be blank.")
    return v


def _require_url(value: Optional[str], label: str) -> str:
    v = _require(value, label)
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError(f"«{label}» must be a valid URL starting with https://")
    return v


# ── Auth helpers ───────────────────────────────────────────────────
def _get_user_from_cookie(request: Request, db: AsyncSession):
    token = request.cookies.get(COOKIE_KEY)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"]), payload.get("role", "user")
    except (JWTError, KeyError, ValueError):
        return None


async def get_current_user_cookie(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    info = _get_user_from_cookie(request, db)
    if not info:
        return None
    user_id, _ = info
    return await db.get(User, user_id)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_KEY, token,
        httponly=True, samesite="lax",
        max_age=60 * 60 * 24,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_KEY)


def _require_admin(user: Optional[User]) -> None:
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _resolve_tags_and_images(events):
    if not isinstance(events, list):
        events = [events]
    for ev in events:
        ev.tags = [et.tag for et in ev.event_tags]
        ev.image_url = s3.presign(ev.image_url)
    return events


def _ctx(request: Request, user: Optional[User], **kwargs) -> dict:
    messages = getattr(request.state, "messages", [])
    return {"request": request, "user": user, "messages": messages, **kwargs}


# ═══════════════════════════════════════════════════════════════════
# PUBLIC PAGES
# ═══════════════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse)
async def page_index(
    request: Request,
    search: Optional[str] = Query(None),
    is_online: Optional[str] = Query(None),
    organizer_id: Optional[str] = Query(None),
    tag_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _organizer_id = int(organizer_id) if organizer_id and organizer_id.strip() else None
    _tag_id       = int(tag_id)       if tag_id       and tag_id.strip()       else None
    query = select(Event).options(
        selectinload(Event.event_tags).selectinload(EventTag.tag)
    )
    if search:
        query = query.where(
            Event.title.ilike(f"%{search}%") | Event.description.ilike(f"%{search}%")
        )
    if is_online == "true":
        query = query.where(Event.is_online == True)
    elif is_online == "false":
        query = query.where(Event.is_online == False)
    if _organizer_id:
        query = query.where(Event.organizer_id == _organizer_id)
    if _tag_id:
        query = query.join(EventTag, Event.id == EventTag.event_id).where(EventTag.tag_id == _tag_id)

    query  = query.order_by(Event.date_start.asc())
    events = (await db.execute(query)).scalars().all()
    _resolve_tags_and_images(list(events))

    organizers       = (await db.execute(select(Organizer).order_by(Organizer.name))).scalars().all()
    tags             = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
    total_events     = (await db.execute(select(func.count()).select_from(Event))).scalar()
    total_organizers = (await db.execute(select(func.count()).select_from(Organizer))).scalar()

    return templates.TemplateResponse("index.html", _ctx(
        request, user,
        events=events, organizers=organizers, tags=tags,
        search=search, is_online=is_online,
        organizer_id=_organizer_id, tag_id=_tag_id,
        total_events=total_events, total_organizers=total_organizers,
    ))


@router.get("/event/{event_id}", response_class=HTMLResponse)
async def page_event_detail(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    _resolve_tags_and_images(event)
    organizer = await db.get(Organizer, event.organizer_id)

    is_bookmarked = False
    if user:
        bm = (await db.execute(
            select(Bookmark).where(
                Bookmark.user_id == user.id, Bookmark.event_id == event_id
            )
        )).scalar_one_or_none()
        is_bookmarked = bm is not None

    return templates.TemplateResponse("event_detail.html", _ctx(
        request, user,
        event=event, organizer=organizer, is_bookmarked=is_bookmarked,
    ))


# ═══════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════

@router.get("/login", response_class=HTMLResponse)
async def page_login(request: Request, user: Optional[User] = Depends(get_current_user_cookie)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", _ctx(request, user))


@router.post("/login")
async def do_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    email = email.strip()
    if not email:
        return templates.TemplateResponse("login.html", _ctx(
            request, None, error="Email is required."
        ), status_code=400)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", _ctx(
            request, None, error="Invalid email or password.", email=email
        ), status_code=400)

    token    = create_access_token({"sub": str(user.id), "role": user.role})
    response = RedirectResponse("/", status_code=302)
    _set_auth_cookie(response, token)
    return response


@router.get("/register", response_class=HTMLResponse)
async def page_register(request: Request, user: Optional[User] = Depends(get_current_user_cookie)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("register.html", _ctx(request, user))


@router.post("/register")
async def do_register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    email = email.strip()
    if not email:
        return templates.TemplateResponse("register.html", _ctx(
            request, None, error="Email is required."
        ), status_code=400)
    if not password or len(password) < 8:
        return templates.TemplateResponse("register.html", _ctx(
            request, None, error="Password must be at least 8 characters.", email=email
        ), status_code=400)

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        return templates.TemplateResponse("register.html", _ctx(
            request, None, error="Email already registered.", email=email
        ), status_code=400)

    new_user = User(email=email, password_hash=hash_password(password), role="user")
    db.add(new_user)
    await db.commit()

    token    = create_access_token({"sub": str(new_user.id), "role": new_user.role})
    response = RedirectResponse("/", status_code=302)
    _set_auth_cookie(response, token)
    return response


@router.get("/logout")
async def do_logout():
    response = RedirectResponse("/", status_code=302)
    _clear_auth_cookie(response)
    return response


# ═══════════════════════════════════════════════════════════════════
# BOOKMARKS
# ═══════════════════════════════════════════════════════════════════

@router.get("/bookmarks", response_class=HTMLResponse)
async def page_bookmarks(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    result = await db.execute(
        select(Bookmark)
        .where(Bookmark.user_id == user.id)
        .options(
            selectinload(Bookmark.event)
            .selectinload(Event.event_tags)
            .selectinload(EventTag.tag)
        )
        .order_by(Bookmark.added_at.desc())
    )
    bookmarks = result.scalars().all()
    for bm in bookmarks:
        _resolve_tags_and_images(bm.event)

    return templates.TemplateResponse("bookmarks.html", _ctx(request, user, bookmarks=bookmarks))


@router.post("/bookmarks/{event_id}")
async def add_bookmark(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    existing = (await db.execute(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.event_id == event_id)
    )).scalar_one_or_none()

    if not existing:
        db.add(Bookmark(user_id=user.id, event_id=event_id))
        await db.commit()

    return RedirectResponse(f"/event/{event_id}", status_code=302)


@router.post("/bookmarks/{event_id}/remove")
async def remove_bookmark(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    bm = (await db.execute(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.event_id == event_id)
    )).scalar_one_or_none()

    if bm:
        await db.delete(bm)
        await db.commit()

    ref = request.headers.get("referer", "/bookmarks")
    return RedirectResponse(ref, status_code=302)


# ═══════════════════════════════════════════════════════════════════
# ADMIN — Dashboard
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin", response_class=HTMLResponse)
async def page_admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    stats = {
        "events":     (await db.execute(select(func.count()).select_from(Event))).scalar(),
        "organizers": (await db.execute(select(func.count()).select_from(Organizer))).scalar(),
        "tags":       (await db.execute(select(func.count()).select_from(Tag))).scalar(),
        "cities":     (await db.execute(select(func.count()).select_from(City))).scalar(),
        "countries":  (await db.execute(select(func.count()).select_from(Country))).scalar(),
        "users":      (await db.execute(select(func.count()).select_from(User))).scalar(),
    }
    return templates.TemplateResponse("admin/dashboard.html", _ctx(
        request, user, stats=stats, active="dashboard"
    ))


# ═══════════════════════════════════════════════════════════════════
# ADMIN — Events
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/events", response_class=HTMLResponse)
async def page_admin_events(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    events = (await db.execute(
        select(Event)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
        .order_by(Event.id.desc())
    )).scalars().all()
    for ev in events:
        ev.tags = [et.tag for et in ev.event_tags]

    return templates.TemplateResponse("admin/events.html", _ctx(
        request, user, events=events, active="events"
    ))


@router.get("/admin/events/new", response_class=HTMLResponse)
async def page_admin_event_new(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    organizers = (await db.execute(select(Organizer).order_by(Organizer.name))).scalars().all()
    cities     = (await db.execute(select(City).order_by(City.name))).scalars().all()
    tags       = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
    return templates.TemplateResponse("admin/event_form.html", _ctx(
        request, user, event=None,
        organizers=organizers, cities=cities, tags=tags,
    ))


async def _event_form_error(request, user, db, event, error, status_code=400):
    organizers = (await db.execute(select(Organizer).order_by(Organizer.name))).scalars().all()
    cities     = (await db.execute(select(City).order_by(City.name))).scalars().all()
    tags       = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
    return templates.TemplateResponse("admin/event_form.html", _ctx(
        request, user, event=event, error=error,
        organizers=organizers, cities=cities, tags=tags,
    ), status_code=status_code)


@router.post("/admin/events/new")
async def do_admin_event_create(
    request: Request,
    title: str = Form(...),
    organizer_id: int = Form(...),
    date_start: datetime = Form(...),
    date_end: Optional[datetime] = Form(None),
    registration_deadline: Optional[datetime] = Form(None),
    price: Decimal = Form(Decimal("0.00")),
    city_id: Optional[int] = Form(None),
    location_address: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_online: Optional[str] = Form(None),
    tag_ids: List[int] = Form([]),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    try:
        title       = _require(title, "Title")
        description = _require(description, "Description")
        website_url = _require_url(website_url, "Website URL")
    except ValueError as exc:
        return await _event_form_error(request, user, db, None, str(exc))

    online = (is_online == "true")
    if not online:
        location_address = _strip(location_address)
        if not location_address:
            return await _event_form_error(
                request, user, db, None,
                "«Location address» is required for in-person events."
            )

    event = Event(
        title=title, organizer_id=organizer_id,
        date_start=date_start, date_end=date_end,
        registration_deadline=registration_deadline,
        price=price, city_id=city_id or None,
        location_address=location_address,
        website_url=website_url, description=description,
        is_online=online,
    )

    if image and image.filename:
        if image.content_type not in s3.ALLOWED_IMG:
            return await _event_form_error(request, user, db, None, "Unsupported image type.")
        contents = await image.read()
        if contents:
            ext    = s3.ALLOWED_IMG[image.content_type]
            s3_key = f"uploads/{uuid.uuid4()}.{ext}"
            try:
                s3.upload_fileobj(io.BytesIO(contents), s3_key, image.content_type)
                event.image_url = s3_key
            except Exception as e:
                logger.error("S3 upload failed: %s", e)

    db.add(event)
    await db.flush()
    for tid in tag_ids:
        db.add(EventTag(event_id=event.id, tag_id=tid))
    await db.commit()
    return RedirectResponse("/admin/events", status_code=302)


@router.get("/admin/events/{event_id}/edit", response_class=HTMLResponse)
async def page_admin_event_edit(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404)

    event.tags      = [et.tag for et in event.event_tags]
    event.image_url = s3.presign(event.image_url)

    organizers = (await db.execute(select(Organizer).order_by(Organizer.name))).scalars().all()
    cities     = (await db.execute(select(City).order_by(City.name))).scalars().all()
    tags       = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
    return templates.TemplateResponse("admin/event_form.html", _ctx(
        request, user, event=event,
        organizers=organizers, cities=cities, tags=tags,
    ))


@router.post("/admin/events/{event_id}/edit")
async def do_admin_event_edit(
    event_id: int,
    request: Request,
    title: str = Form(...),
    organizer_id: int = Form(...),
    date_start: datetime = Form(...),
    date_end: Optional[datetime] = Form(None),
    registration_deadline: Optional[datetime] = Form(None),
    price: Decimal = Form(Decimal("0.00")),
    city_id: Optional[int] = Form(None),
    location_address: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_online: Optional[str] = Form(None),
    tag_ids: List[int] = Form([]),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)

    async def _fetch_event_for_form():
        res = await db.execute(
            select(Event).where(Event.id == event_id)
            .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
        )
        ev = res.scalar_one_or_none()
        if ev:
            ev.tags      = [et.tag for et in ev.event_tags]
            ev.image_url = s3.presign(ev.image_url)
        return ev

    try:
        title       = _require(title, "Title")
        description = _require(description, "Description")
        website_url = _require_url(website_url, "Website URL")
    except ValueError as exc:
        ev = await _fetch_event_for_form()
        return await _event_form_error(request, user, db, ev, str(exc))

    online = (is_online == "true")
    if not online:
        location_address = _strip(location_address)
        if not location_address:
            ev = await _fetch_event_for_form()
            return await _event_form_error(
                request, user, db, ev,
                "«Location address» is required for in-person events."
            )

    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.event_tags).selectinload(EventTag.tag))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404)

    updates = {
        "title": title, "organizer_id": organizer_id,
        "date_start": date_start, "date_end": date_end,
        "registration_deadline": registration_deadline,
        "price": price, "city_id": city_id or None,
        "location_address": location_address,
        "website_url": website_url, "description": description,
        "is_online": online,
    }
    for field, new_val in updates.items():
        old_val = getattr(event, field, None)
        if str(old_val) != str(new_val):
            db.add(EventAuditLog(
                event_id=event_id, changed_by=user.id,
                changed_column=field, old_value=str(old_val), new_value=str(new_val),
            ))
        setattr(event, field, new_val)

    if image and image.filename and image.content_type in s3.ALLOWED_IMG:
        contents = await image.read()
        if contents:
            ext    = s3.ALLOWED_IMG[image.content_type]
            s3_key = f"uploads/{uuid.uuid4()}.{ext}"
            try:
                s3.upload_fileobj(io.BytesIO(contents), s3_key, image.content_type)
                event.image_url = s3_key
            except Exception as e:
                logger.error("S3 upload failed: %s", e)

    await db.execute(EventTag.__table__.delete().where(EventTag.event_id == event_id))
    for tid in tag_ids:
        db.add(EventTag(event_id=event_id, tag_id=tid))

    event.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse("/admin/events", status_code=302)


@router.post("/admin/events/{event_id}/delete")
async def do_admin_event_delete(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    event = await db.get(Event, event_id)
    if event:
        s3.delete_object(event.image_url)
        await db.delete(event)
        await db.commit()
    return RedirectResponse("/admin/events", status_code=302)


# ═══════════════════════════════════════════════════════════════════
# ADMIN — Tags
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/tags", response_class=HTMLResponse)
async def page_admin_tags(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    tags = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
    return templates.TemplateResponse("admin/tags.html", _ctx(
        request, user, tags=tags, active="tags"
    ))


@router.post("/admin/tags")
async def do_admin_tag_create(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    name = _strip(name)
    if not name:
        tags = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
        return templates.TemplateResponse("admin/tags.html", _ctx(
            request, user, tags=tags, error="Tag name cannot be blank."
        ), status_code=400)

    existing = (await db.execute(select(Tag).where(Tag.name == name))).scalar_one_or_none()
    if existing:
        tags = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
        return templates.TemplateResponse("admin/tags.html", _ctx(
            request, user, tags=tags, error=f"Tag '{name}' already exists."
        ), status_code=400)

    db.add(Tag(name=name))
    await db.commit()
    return RedirectResponse("/admin/tags", status_code=302)


@router.post("/admin/tags/{tag_id}/delete")
async def do_admin_tag_delete(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    tag = await db.get(Tag, tag_id)
    if tag:
        await db.delete(tag)
        await db.commit()
    return RedirectResponse("/admin/tags", status_code=302)


# ═══════════════════════════════════════════════════════════════════
# ADMIN — Cities
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/cities", response_class=HTMLResponse)
async def page_admin_cities(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    cities    = (await db.execute(
        select(City).options(selectinload(City.country)).order_by(City.name)
    )).scalars().all()
    countries = (await db.execute(select(Country).order_by(Country.name))).scalars().all()
    return templates.TemplateResponse("admin/cities.html", _ctx(
        request, user, cities=cities, countries=countries, active="cities"
    ))


@router.post("/admin/cities")
async def do_admin_city_create(
    request: Request,
    name: str = Form(...),
    country_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)

    async def _city_error(msg: str):
        cities    = (await db.execute(
            select(City).options(selectinload(City.country)).order_by(City.name)
        )).scalars().all()
        countries = (await db.execute(select(Country).order_by(Country.name))).scalars().all()
        return templates.TemplateResponse("admin/cities.html", _ctx(
            request, user, cities=cities, countries=countries,
            active="cities", error=msg,
        ), status_code=400)

    name = _strip(name)
    if not name:
        return await _city_error("City name cannot be blank.")

    country = await db.get(Country, country_id)
    if not country:
        return await _city_error("Please select a valid country.")

    existing = (await db.execute(
        select(City).where(City.name == name, City.country_id == country_id)
    )).scalar_one_or_none()
    if existing:
        return await _city_error(f"City '{name}' already exists in {country.name}.")

    db.add(City(name=name, country_id=country_id))
    await db.commit()
    return RedirectResponse("/admin/cities", status_code=302)


@router.post("/admin/cities/{city_id}/delete")
async def do_admin_city_delete(
    city_id: int,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    city = await db.get(City, city_id)
    if city:
        await db.delete(city)
        await db.commit()
    return RedirectResponse("/admin/cities", status_code=302)


# ═══════════════════════════════════════════════════════════════════
# ADMIN — Organizers
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/organizers", response_class=HTMLResponse)
async def page_admin_organizers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    organizers = (await db.execute(select(Organizer).order_by(Organizer.name))).scalars().all()
    return templates.TemplateResponse("admin/organizers.html", _ctx(
        request, user, organizers=organizers, active="organizers"
    ))


@router.post("/admin/organizers")
async def do_admin_organizer_create(
    request: Request,
    name: str = Form(...),
    website: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)

    async def _org_error(msg: str):
        orgs = (await db.execute(select(Organizer).order_by(Organizer.name))).scalars().all()
        return templates.TemplateResponse("admin/organizers.html", _ctx(
            request, user, organizers=orgs, error=msg
        ), status_code=400)

    try:
        name          = _require(name, "Name")
        website       = _require_url(website, "Website")
        contact_email = _require(contact_email, "Contact email")
        description   = _require(description, "Description")
    except ValueError as exc:
        return await _org_error(str(exc))

    if "@" not in contact_email:
        return await _org_error("«Contact email» must be a valid email address.")

    existing = (await db.execute(select(Organizer).where(Organizer.name == name))).scalar_one_or_none()
    if existing:
        return await _org_error(f"Organizer '{name}' already exists.")

    db.add(Organizer(name=name, website=website, contact_email=contact_email, description=description))
    await db.commit()
    return RedirectResponse("/admin/organizers", status_code=302)


# ═══════════════════════════════════════════════════════════════════
# ADMIN — Audit Log
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/audit", response_class=HTMLResponse)
async def page_admin_audit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    logs = (await db.execute(
        select(EventAuditLog).order_by(EventAuditLog.change_date.desc()).limit(200)
    )).scalars().all()
    return templates.TemplateResponse("admin/audit.html", _ctx(
        request, user, logs=logs, active="audit"
    ))


# ═══════════════════════════════════════════════════════════════════
# ADMIN — Countries
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/countries", response_class=HTMLResponse)
async def page_admin_countries(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    countries = (await db.execute(
        select(Country).options(selectinload(Country.cities)).order_by(Country.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/countries.html", _ctx(
        request, user, countries=countries, active="countries"
    ))


@router.post("/admin/countries")
async def do_admin_country_create(
    request: Request,
    name: str = Form(...),
    iso_code: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)

    async def _country_error(msg: str):
        countries = (await db.execute(
            select(Country).options(selectinload(Country.cities)).order_by(Country.name)
        )).scalars().all()
        return templates.TemplateResponse("admin/countries.html", _ctx(
            request, user, countries=countries, active="countries", error=msg,
        ), status_code=400)

    try:
        name = _require(name, "Country name")
    except ValueError as exc:
        return await _country_error(str(exc))

    iso = _strip(iso_code)
    if iso:
        iso = iso.upper()
        if not (2 <= len(iso) <= 3 and iso.isalpha()):
            return await _country_error("ISO code must be 2–3 letters (e.g. DE, UKR).")
        existing_iso = (await db.execute(
            select(Country).where(Country.iso_code == iso)
        )).scalar_one_or_none()
        if existing_iso:
            return await _country_error(f"ISO code '{iso}' is already used by {existing_iso.name}.")

    existing_name = (await db.execute(
        select(Country).where(Country.name == name)
    )).scalar_one_or_none()
    if existing_name:
        return await _country_error(f"Country '{name}' already exists.")

    db.add(Country(name=name, iso_code=iso or None))
    await db.commit()
    return RedirectResponse("/admin/countries", status_code=302)


@router.post("/admin/countries/{country_id}/delete")
async def do_admin_country_delete(
    country_id: int,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_cookie),
):
    _require_admin(user)
    country = await db.get(Country, country_id)
    if country:
        await db.delete(country)
        await db.commit()
    return RedirectResponse("/admin/countries", status_code=302)