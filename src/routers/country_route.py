from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import require_admin
from src.core.database import get_db
from src.models.country import Country
from src.models.user import User
from src.schemas.country_schema import CountryCreate, CountryOut

router = APIRouter(prefix="/api/v1/countries", tags=["Countries"])


@router.get("", response_model=List[CountryOut])
async def list_countries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Country).order_by(Country.name))
    return result.scalars().all()


@router.get("/{country_id}", response_model=CountryOut)
async def get_country(country_id: int, db: AsyncSession = Depends(get_db)):
    country = await db.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


@router.post("", response_model=CountryOut, status_code=201)
async def create_country(
    payload: CountryCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    name = payload.name.strip()
    iso  = payload.iso_code.strip().upper() if payload.iso_code else None

    existing_name = (
        await db.execute(select(Country).where(Country.name == name))
    ).scalar_one_or_none()
    if existing_name:
        raise HTTPException(status_code=409, detail="Country with this name already exists")

    if iso:
        existing_iso = (
            await db.execute(select(Country).where(Country.iso_code == iso))
        ).scalar_one_or_none()
        if existing_iso:
            raise HTTPException(status_code=409, detail="Country with this ISO code already exists")

    country = Country(name=name, iso_code=iso)
    db.add(country)
    await db.commit()
    await db.refresh(country)
    return country


@router.delete("/{country_id}", status_code=204)
async def delete_country(
    country_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    country = await db.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    await db.delete(country)
    await db.commit()
    return None
