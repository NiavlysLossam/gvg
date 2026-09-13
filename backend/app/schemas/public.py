import json
import uuid
from datetime import datetime
from typing import Optional, List, Literal, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.spot import (
    GeoJSONPolygon,
    wkb_or_str_to_geojson_polygon,
)


class PublicSpotProperties(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    label: str
    linear_meters: float
    price_cents: int
    price: float
    status: Literal["available", "locked", "reserved", "blocked"]
    is_offline: bool = False
    locked_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PublicSpotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: GeoJSONPolygon
    properties: PublicSpotProperties


class PublicSpotFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[PublicSpotFeature] = []


class LockSpotRequest(BaseModel):
    session_token: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Anonymous client session UUID token",
    )


class UnlockSpotRequest(BaseModel):
    session_token: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Anonymous client session UUID token",
    )


class CartSpotItem(BaseModel):
    id: uuid.UUID
    label: str
    linear_meters: float
    price_cents: int
    price: float
    locked_until: datetime

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    session_token: str
    spots: List[CartSpotItem] = []
    total_count: int = 0
    total_linear_meters: float = 0.0
    total_price_cents: int = 0
    total_price: float = 0.0
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PublicEventResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    description: Optional[str] = None
    map_type: Literal["geographic", "planar"] = "geographic"
    background_image_url: Optional[str] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    default_zoom: Optional[int] = None
    price_per_meter_cents: int
    price_per_meter: float = Field(..., description="Tarif au mètre en euros")
    
    start_date: datetime
    end_date: datetime
    setup_start_time: Optional[str] = "06:00"
    setup_end_time: Optional[str] = "08:00"
    public_start_time: Optional[str] = "08:00"
    public_end_time: Optional[str] = "18:00"
    
    location_address: Optional[str] = None
    organizer_email: Optional[str] = None
    rules_text: Optional[str] = None
    status: str = "published"
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_price_per_meter(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "price_per_meter" not in data and "price_per_meter_cents" in data:
                cents = data.get("price_per_meter_cents")
                if cents is not None:
                    data["price_per_meter"] = round(cents / 100.0, 2)
            return data

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


def public_spot_to_feature(
    spot: Any,
    effective_status: str,
    geojson_str: Optional[str] = None,
    is_offline: bool = False,
) -> PublicSpotFeature:
    """Converts a Spot instance with computed effective_status to a public GeoJSON Feature."""
    if geojson_str:
        geom_dict = json.loads(geojson_str)
        polygon = GeoJSONPolygon(**geom_dict)
    else:
        polygon = wkb_or_str_to_geojson_polygon(spot.geom)

    return PublicSpotFeature(
        id=spot.id,
        geometry=polygon,
        properties=PublicSpotProperties(
            id=spot.id,
            event_id=spot.event_id,
            label=spot.label,
            linear_meters=spot.linear_meters,
            price_cents=spot.price_cents,
            price=spot.price,
            status=effective_status,
            is_offline=is_offline,
            locked_until=spot.locked_until if effective_status == "locked" else None,
            created_at=spot.created_at,
            updated_at=spot.updated_at,
        ),
    )


def public_spots_to_feature_collection(
    spots_data: list,
) -> PublicSpotFeatureCollection:
    """Converts list of (Spot, geojson_str, effective_status, [order_payment_method]) tuples/rows to PublicSpotFeatureCollection."""
    features = []
    for item in spots_data:
        is_offline = False
        if hasattr(item, "__getitem__") and not isinstance(item, (str, bytes)):
            spot = item[0]
            geojson_str = item[1] if len(item) > 1 else None
            eff_status = item[2] if len(item) > 2 else spot.status
            if len(item) > 3:
                order_pm = item[3]
                is_offline = (eff_status == "reserved" and order_pm in ("check", "cash", "other"))
        else:
            spot = item
            geojson_str = None
            eff_status = getattr(spot, "effective_status", spot.status)
            is_offline = getattr(spot, "is_offline", False)
        features.append(public_spot_to_feature(spot, eff_status, geojson_str, is_offline=is_offline))
    return PublicSpotFeatureCollection(features=features)

