import uuid
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class EventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Titre de l'événement")
    description: Optional[str] = Field(None, max_length=5000, description="Description générale")
    map_type: Literal["geographic", "planar"] = Field("geographic", description="Type de fond de plan: 'geographic' ou 'planar'")
    background_image_url: Optional[str] = Field(None, max_length=1024, description="URL de l'image de fond pour mode planaire")
    
    start_date: datetime = Field(..., description="Date et heure de début de l'événement")
    end_date: datetime = Field(..., description="Date et heure de fin de l'événement")
    
    setup_start_time: Optional[str] = Field("06:00", max_length=10, description="Heure de début d'installation des exposants")
    setup_end_time: Optional[str] = Field("08:00", max_length=10, description="Heure de fin d'installation des exposants")
    public_start_time: Optional[str] = Field("08:00", max_length=10, description="Heure d'ouverture au public")
    public_end_time: Optional[str] = Field("18:00", max_length=10, description="Heure de fermeture au public")
    
    location_address: Optional[str] = Field(None, max_length=500, description="Adresse physique de l'événement")
    organizer_email: Optional[str] = Field(None, max_length=255, description="Email de contact de l'organisateur")
    
    manual_approval_required: bool = Field(False, description="Modération manuelle requise pour les réservations")
    rules_text: Optional[str] = Field(None, max_length=10000, description="Règlement intérieur de l'événement")
    status: Literal["draft", "published", "archived"] = Field("draft", description="Statut de l'événement: draft, published, archived")


class EventCreate(EventBase):
    price_per_meter: Optional[float] = Field(None, description="Tarif au mètre linéaire en euros (ex: 4.00)")
    price_per_meter_cents: Optional[int] = Field(None, description="Tarif au mètre linéaire en centimes (ex: 400)")

    @model_validator(mode="after")
    def validate_dates_and_price(self) -> "EventCreate":
        # Date range validation
        if _to_utc(self.end_date) < _to_utc(self.start_date):
            raise ValueError("end_date must be greater than or equal to start_date")

        # Price validation
        if self.price_per_meter is not None:
            if self.price_per_meter <= 0:
                raise ValueError("price_per_meter must be greater than 0")
            if self.price_per_meter_cents is None:
                self.price_per_meter_cents = int(round(self.price_per_meter * 100))

        if self.price_per_meter_cents is not None:
            if self.price_per_meter_cents <= 0:
                raise ValueError("price_per_meter_cents must be greater than 0")
        else:
            raise ValueError("Price per meter (price_per_meter or price_per_meter_cents) is required")

        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    map_type: Optional[Literal["geographic", "planar"]] = None
    background_image_url: Optional[str] = Field(None, max_length=1024)
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    setup_start_time: Optional[str] = Field(None, max_length=10)
    setup_end_time: Optional[str] = Field(None, max_length=10)
    public_start_time: Optional[str] = Field(None, max_length=10)
    public_end_time: Optional[str] = Field(None, max_length=10)
    
    location_address: Optional[str] = Field(None, max_length=500)
    organizer_email: Optional[str] = Field(None, max_length=255)
    manual_approval_required: Optional[bool] = None
    rules_text: Optional[str] = Field(None, max_length=10000)
    status: Optional[Literal["draft", "published", "archived"]] = None
    
    price_per_meter: Optional[float] = None
    price_per_meter_cents: Optional[int] = None

    @model_validator(mode="after")
    def validate_update(self) -> "EventUpdate":
        if self.start_date and self.end_date and _to_utc(self.end_date) < _to_utc(self.start_date):
            raise ValueError("end_date must be greater than or equal to start_date")
        if self.price_per_meter is not None:
            if self.price_per_meter <= 0:
                raise ValueError("price_per_meter must be greater than 0")
            if self.price_per_meter_cents is None:
                self.price_per_meter_cents = int(round(self.price_per_meter * 100))
        if self.price_per_meter_cents is not None and self.price_per_meter_cents <= 0:
            raise ValueError("price_per_meter_cents must be greater than 0")
        return self


class EventResponse(EventBase):
    id: uuid.UUID
    slug: str
    price_per_meter_cents: int
    price_per_meter: float = Field(..., description="Prix par mètre en euros")
    stripe_account_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_price_per_meter(cls, data: any) -> any:
        if isinstance(data, dict):
            if "price_per_meter" not in data and "price_per_meter_cents" in data:
                cents = data.get("price_per_meter_cents")
                if cents is not None:
                    data["price_per_meter"] = round(cents / 100.0, 2)
            return data
        
        # If it's an ORM object or object with price_per_meter property
        if hasattr(data, "price_per_meter"):
            return data

        cents = getattr(data, "price_per_meter_cents", None)
        if cents is not None:
            if hasattr(data, "__table__"):
                data_dict = {
                    c.name: getattr(data, c.name)
                    for c in data.__table__.columns
                }
                data_dict["price_per_meter"] = round(cents / 100.0, 2)
                return data_dict
            elif hasattr(data, "__dict__"):
                data_dict = dict(data.__dict__)
                data_dict["price_per_meter"] = round(cents / 100.0, 2)
                return data_dict
        return data


class EventListResponse(BaseModel):
    items: List[EventResponse]
    total: int

