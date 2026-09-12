import re
import json
import struct
import uuid
from datetime import datetime
from typing import Optional, List, Literal, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]] = Field(
        ...,
        description="Coordonnées du polygone : liste d'anneaux linéaires [[[x, y], ...]]",
    )

    @field_validator("coordinates")
    @classmethod
    def validate_polygon_coordinates(cls, v: List[List[List[float]]]) -> List[List[List[float]]]:
        if not v or len(v) == 0:
            raise ValueError("Le polygone doit contenir au moins un anneau linéaire")
        for ring in v:
            if not ring or len(ring) < 3:
                raise ValueError("Chaque anneau linéaire doit comporter au moins 3 points")
            for pt in ring:
                if len(pt) < 2:
                    raise ValueError("Chaque coordonnée doit contenir au moins 2 valeurs [x, y]")
        return v


class SpotProperties(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    label: str
    linear_meters: float
    price_cents: int
    price: float
    status: Literal["available", "locked", "reserved", "blocked"]
    locked_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SpotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: GeoJSONPolygon
    properties: SpotProperties


class SpotFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[SpotFeature] = []


class SpotCreate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100, description="Numéro ou étiquette du stand")
    linear_meters: Optional[float] = Field(None, description="Métrage linéaire du stand (> 0)")
    price_cents: Optional[int] = Field(None, ge=0, description="Tarif en centimes (optionnel, calculé auto)")
    price: Optional[float] = Field(None, ge=0, description="Tarif en euros (optionnel)")
    geometry: Optional[GeoJSONPolygon] = Field(None, description="Géométrie GeoJSON du stand")

    @model_validator(mode="before")
    @classmethod
    def extract_from_feature(cls, data: Any) -> Any:
        """Allow passing a GeoJSON Feature or flat dict."""
        if isinstance(data, dict):
            props = data.get("properties")
            if isinstance(props, dict):
                merged = {**props, **data}
                if "geometry" in data:
                    merged["geometry"] = data["geometry"]
                return merged
        return data

    @model_validator(mode="after")
    def validate_required_fields(self) -> "SpotCreate":
        if not self.label or not self.label.strip():
            raise ValueError("label est requis")
        if self.linear_meters is None or self.linear_meters <= 0:
            raise ValueError("linear_meters doit être supérieur à 0")
        if not self.geometry:
            raise ValueError("geometry est requise")
        if self.price is not None and self.price_cents is None:
            self.price_cents = int(round(self.price * 100))
        return self


class SpotUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    linear_meters: Optional[float] = Field(None, gt=0, description="Métrage linéaire (> 0)")
    price_cents: Optional[int] = Field(None, ge=0)
    price: Optional[float] = Field(None, ge=0)
    geometry: Optional[GeoJSONPolygon] = None
    status: Optional[Literal["available", "locked", "reserved", "blocked"]] = None

    @field_validator("label")
    @classmethod
    def validate_label_not_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Le libellé ne peut pas être vide")
            return stripped
        return v

    @model_validator(mode="before")
    @classmethod
    def extract_from_feature(cls, data: Any) -> Any:
        if isinstance(data, dict):
            props = data.get("properties")
            if isinstance(props, dict):
                merged = {**props, **data}
                if "geometry" in data:
                    merged["geometry"] = data["geometry"]
                return merged
        return data

    @model_validator(mode="after")
    def validate_update_fields(self) -> "SpotUpdate":
        if self.price is not None and self.price_cents is None:
            self.price_cents = int(round(self.price * 100))
        return self


class SpotBatchCreate(BaseModel):
    spots: List[SpotCreate] = Field(
        ..., min_length=1, max_length=500, description="Liste des stands à créer"
    )

    @model_validator(mode="before")
    @classmethod
    def extract_from_features(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "spots" in data:
                return data
            if "features" in data:
                return {"spots": data["features"]}
        elif isinstance(data, list):
            return {"spots": data}
        return data


class SpotBatchCreateResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[SpotFeature] = []
    created_count: int = 0


class SpotRenumberItem(BaseModel):
    spot_id: uuid.UUID = Field(..., description="Identifiant unique du stand")
    label: str = Field(..., min_length=1, max_length=100, description="Nouveau libellé du stand")

    @field_validator("label")
    @classmethod
    def validate_label_not_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Le libellé ne peut pas être vide")
        return stripped


class SpotBatchRenumber(BaseModel):
    spot_ids: Optional[List[uuid.UUID]] = Field(
        None, max_length=500, description="Liste ordonnée des identifiants de stands à renuméroter"
    )
    prefix: Optional[str] = Field(None, max_length=80, description="Préfixe d'allée (ex: 'Allée A - ')")
    start_number: Optional[int] = Field(1, ge=0, description="Numéro de départ (ex: 1)")
    zero_padding: Optional[int] = Field(2, ge=0, le=10, description="Longueur du padding zéro (ex: 2 pour 01)")
    renumberings: Optional[List[SpotRenumberItem]] = Field(
        None, max_length=500, description="Liste explicite d'associations stand -> nouveau libellé"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data_copy = dict(data)
            if "pad" in data_copy and "zero_padding" not in data_copy:
                data_copy["zero_padding"] = data_copy.pop("pad")
            if "start" in data_copy and "start_number" not in data_copy:
                data_copy["start_number"] = data_copy.pop("start")
            return data_copy
        return data

    @model_validator(mode="after")
    def validate_payload(self) -> "SpotBatchRenumber":
        if not self.spot_ids and not self.renumberings:
            raise ValueError("Au moins 'spot_ids' ou 'renumberings' doit être fourni")
        if self.spot_ids is not None and len(self.spot_ids) == 0:
            raise ValueError("'spot_ids' ne peut pas être vide")
        if self.renumberings is not None and len(self.renumberings) == 0:
            raise ValueError("'renumberings' ne peut pas être vide")
        if self.spot_ids is not None:
            if len(self.spot_ids) != len(set(self.spot_ids)):
                raise ValueError("La liste 'spot_ids' contient des identifiants de stands dupliqués")
            prefix_len = len(self.prefix or "")
            pad = self.zero_padding if self.zero_padding is not None else 2
            max_num = (self.start_number or 1) + len(self.spot_ids) - 1
            max_num_len = max(len(str(max_num)), pad)
            if prefix_len + max_num_len > 100:
                raise ValueError("Le libellé généré dépasserait la longueur maximale de 100 caractères")
        if self.renumberings is not None:
            seen_ids = set()
            for item in self.renumberings:
                if item.spot_id in seen_ids:
                    raise ValueError("La liste 'renumberings' contient des identifiants de stands dupliqués")
                seen_ids.add(item.spot_id)
        return self


class SpotBatchRenumberResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[SpotFeature] = []
    updated_count: int = 0


# Geometry helper utilities
def geojson_to_wkt_polygon(polygon: Union[GeoJSONPolygon, dict]) -> str:
    """Converts a GeoJSON Polygon coordinates array to WKT POLYGON((x y, ...))."""
    if isinstance(polygon, GeoJSONPolygon):
        coords = polygon.coordinates
    elif isinstance(polygon, dict):
        coords = polygon.get("coordinates", [])
    else:
        coords = polygon

    rings = []
    for ring in coords:
        if len(ring) < 3:
            raise ValueError("Chaque anneau linéaire doit comporter au moins 3 points")
        ring_pts = list(ring)
        # Ensure linear ring is closed
        if ring_pts[0][0] != ring_pts[-1][0] or ring_pts[0][1] != ring_pts[-1][1]:
            ring_pts.append(ring_pts[0])
        if len(ring_pts) < 4:
            raise ValueError("Un anneau fermé doit comporter au moins 4 points")
        ring_str = ", ".join(f"{float(pt[0])} {float(pt[1])}" for pt in ring_pts)
        rings.append(f"({ring_str})")
    return f"POLYGON({', '.join(rings)})"


def parse_wkt_polygon(wkt: str) -> GeoJSONPolygon:
    """Parses WKT POLYGON((x y, ...), ...) into a GeoJSONPolygon."""
    cleaned = wkt.strip()
    match = re.search(r"POLYGON\s*\(\s*(.*)\s*\)", cleaned, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"WKT polygone invalide : {wkt}")
    inner = match.group(1).strip()
    ring_matches = re.findall(r"\((.*?)\)", inner)
    if not ring_matches:
        raise ValueError(f"WKT polygone sans anneaux valides : {wkt}")
    rings = []
    for ring_str in ring_matches:
        points = []
        for pair in ring_str.split(","):
            parts = pair.strip().split()
            if len(parts) >= 2:
                points.append([float(parts[0]), float(parts[1])])
        if len(points) >= 3:
            rings.append(points)
    if not rings:
        raise ValueError(f"WKT polygone sans coordonnées valides : {wkt}")
    return GeoJSONPolygon(type="Polygon", coordinates=rings)


def wkb_bytes_to_geojson_polygon(wkb_bytes: bytes) -> GeoJSONPolygon:
    """Parses standard WKB or EWKB bytes into a GeoJSONPolygon without external C libraries."""
    byte_order = wkb_bytes[0]
    endian = "<" if byte_order == 1 else ">"
    geom_type = struct.unpack(endian + "I", wkb_bytes[1:5])[0]
    offset = 5
    # EWKB SRID flag
    if geom_type & 0x20000000:
        offset += 4
        geom_type &= 0x1FFFFFFF
    if geom_type != 3:  # 3 = Polygon
        raise ValueError(f"Attendu type Polygon (3), reçu {geom_type}")
    num_rings = struct.unpack(endian + "I", wkb_bytes[offset : offset + 4])[0]
    offset += 4
    rings = []
    for _ in range(num_rings):
        num_points = struct.unpack(endian + "I", wkb_bytes[offset : offset + 4])[0]
        offset += 4
        ring = []
        for _ in range(num_points):
            x, y = struct.unpack(endian + "dd", wkb_bytes[offset : offset + 16])
            offset += 16
            ring.append([x, y])
        rings.append(ring)
    return GeoJSONPolygon(type="Polygon", coordinates=rings)


def wkb_or_str_to_geojson_polygon(geom_val: Any) -> GeoJSONPolygon:
    """Parses various geometry representations into a GeoJSONPolygon."""
    if isinstance(geom_val, GeoJSONPolygon):
        return geom_val
    if isinstance(geom_val, dict):
        return GeoJSONPolygon(**geom_val)
    if isinstance(geom_val, str):
        geom_val_strip = geom_val.strip()
        if geom_val_strip.startswith("{"):
            return GeoJSONPolygon(**json.loads(geom_val_strip))
        if geom_val_strip.upper().startswith("POLYGON"):
            return parse_wkt_polygon(geom_val_strip)
        try:
            raw_bytes = bytes.fromhex(geom_val_strip)
            return wkb_bytes_to_geojson_polygon(raw_bytes)
        except Exception:
            pass

    if hasattr(geom_val, "data"):
        data = geom_val.data
        if isinstance(data, str):
            data = bytes.fromhex(data)
        elif not isinstance(data, bytes):
            data = bytes(data)
        return wkb_bytes_to_geojson_polygon(data)

    raise ValueError(f"Impossible de convertir la géométrie {type(geom_val)} en GeoJSON")


def spot_to_feature(spot: Any, geojson_str: Optional[str] = None) -> SpotFeature:
    """Converts a Spot SQLAlchemy model instance to a GeoJSON Feature."""
    if geojson_str:
        geom_dict = json.loads(geojson_str)
        polygon = GeoJSONPolygon(**geom_dict)
    else:
        polygon = wkb_or_str_to_geojson_polygon(spot.geom)

    return SpotFeature(
        id=spot.id,
        geometry=polygon,
        properties=SpotProperties(
            id=spot.id,
            event_id=spot.event_id,
            label=spot.label,
            linear_meters=spot.linear_meters,
            price_cents=spot.price_cents,
            price=spot.price,
            status=spot.status,
            locked_until=spot.locked_until,
            created_at=spot.created_at,
            updated_at=spot.updated_at,
        ),
    )


def spots_to_feature_collection(spots_with_geojson: list) -> SpotFeatureCollection:
    """Converts list of (Spot, geojson_str) tuples/Rows or Spot objects to GeoJSON FeatureCollection."""
    features = []
    for item in spots_with_geojson:
        if hasattr(item, "__getitem__") and not isinstance(item, (str, bytes)):
            try:
                spot = item[0]
                geojson_str = item[1] if len(item) > 1 else None
            except (IndexError, TypeError):
                spot = item
                geojson_str = None
        else:
            spot = item
            geojson_str = None
        features.append(spot_to_feature(spot, geojson_str))
    return SpotFeatureCollection(features=features)
