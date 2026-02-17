from datetime import datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Text, Boolean, TIMESTAMP, Numeric, func
from src.models.base import Base

class Event(Base):
    __tablename__ = "events"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Основні поля (NOT NULL в SQL)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    organizer_id: Mapped[int] = mapped_column(Integer, nullable=False) # FK на organizers
    date_start: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    
    # Nullable поля (можуть бути NULL в SQL)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Price (Default 0.00 в SQL)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)

    # Часові мітки
    date_end: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    registration_deadline: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)

    # Локація
    city_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # FK на cities (може бути NULL)
    location_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    # Системні поля (автоматично заповнюються БД, але читаємо їх тут)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, onupdate=func.now())