from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth import require_admin
from src.core.database import get_db
from src.models.city import City
from src.models.country import Country
from src.models.user import User
from src.schemas.city_schema import CityCreate, CityOut

router = APIRouter(prefix="/api/v1/cities", tags=["Cities"])


@router.get("", response_model=List[CityOut])
async def list_cities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(City).order_by(City.name))
    return result.scalars().all()


@router.get("/{city_id}", response_model=CityOut)
async def get_city(city_id: int, db: AsyncSession = Depends(get_db)):
    city = await db.get(City, city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    return city


@router.post("", response_model=CityOut, status_code=201)
async def create_city(
    payload: CityCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # verify country exists
    country = await db.get(Country, payload.country_id)
    if not country:
        raise HTTPException(status_code=400, detail="Country not found")

    existing = (
        await db.execute(
            select(City).where(
                City.name == payload.name.strip(),
                City.country_id == payload.country_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="City already exists in this country")

    city = City(name=payload.name.strip(), country_id=payload.country_id)
    db.add(city)
    await db.commit()
    await db.refresh(city)
    return city


@router.delete("/{city_id}", status_code=204)
async def delete_city(
    city_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    city = await db.get(City, city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    await db.delete(city)
    await db.commit()
    return None
