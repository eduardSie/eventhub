from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    organizer_id: int
    
    # city_id тепер Optional, бо в SQL ON DELETE SET NULL
    city_id: Optional[int] = None 
    
    website_url: Optional[str] = None
    price: Decimal = Decimal("0.00")
    date_start: datetime
    date_end: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    location_address: Optional[str] = None
    is_online: bool = False

class EventCreate(EventBase):
    """Використовується при створенні"""
    pass

class EventOut(EventBase):
    id: int
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True