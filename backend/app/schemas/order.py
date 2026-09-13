import re
import uuid
from datetime import datetime
from typing import Optional, List, Any, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class GuestOrderCreate(BaseModel):
    session_token: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Anonymous client session UUID token",
    )
    first_name: str = Field(..., min_length=1, max_length=100, description="Prénom")
    last_name: str = Field(..., min_length=1, max_length=100, description="Nom")
    email: str = Field(..., min_length=5, max_length=255, description="Adresse email valide")
    phone: str = Field(..., min_length=5, max_length=50, description="Numéro de téléphone portable")
    street_address: str = Field(..., min_length=2, max_length=255, description="Adresse postale")
    postal_code: str = Field(..., min_length=2, max_length=20, description="Code postal")
    city: str = Field(..., min_length=1, max_length=100, description="Ville")
    honor_declaration_accepted: bool = Field(
        ...,
        description="Attestation sur l'honneur obligatoire (art. L310-2 du Code de commerce)",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("L'adresse email est obligatoire.")
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("L'adresse email est invalide.")
        return cleaned

    @field_validator("first_name", "last_name", "street_address", "city")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        cleaned = v.strip()
        if not cleaned:
            field_name = info.field_name
            labels = {
                "first_name": "Le prénom est obligatoire.",
                "last_name": "Le nom est obligatoire.",
                "street_address": "L'adresse est obligatoire.",
                "city": "La ville est obligatoire.",
            }
            msg = labels.get(field_name, f"Le champ {field_name} est obligatoire.")
            raise ValueError(msg)
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        digits_only = re.sub(r"\D", "", cleaned)
        if len(digits_only) < 8 or len(digits_only) > 15:
            raise ValueError("Le numéro de téléphone doit contenir entre 8 et 15 chiffres.")
        return cleaned

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Le code postal est obligatoire.")
        if not re.match(r"^[0-9A-Za-z\s-]{2,10}$", cleaned):
            raise ValueError("Le code postal est invalide.")
        return cleaned

    @field_validator("honor_declaration_accepted")
    @classmethod
    def validate_honor_declaration(cls, v: bool) -> bool:
        if not v:
            raise ValueError("L'attestation sur l'honneur est obligatoire pour participer au vide-grenier.")
        return v


class BookingItemOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    spot_id: uuid.UUID
    price_cents: int
    price: float
    spot_label: Optional[str] = None
    spot_linear_meters: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_spot_info(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            spot = getattr(data, "spot", None)
            cents = getattr(data, "price_cents", 0)
            return {
                "id": data.id,
                "order_id": data.order_id,
                "spot_id": data.spot_id,
                "price_cents": cents,
                "price": round(cents / 100.0, 2),
                "spot_label": spot.label if spot else None,
                "spot_linear_meters": spot.linear_meters if spot else None,
                "created_at": getattr(data, "created_at", None),
            }
        return data


class OrderOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    order_number: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: str
    street_address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    honor_declaration_accepted: bool
    honor_declaration_accepted_at: datetime
    total_price_cents: int
    total_price: float
    status: str
    payment_method: str
    offline_payment_reference: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    access_token: str
    cancellation_reason: Optional[str] = None
    cancellation_comment: Optional[str] = None
    cancellation_requested_at: Optional[datetime] = None
    items: List[BookingItemOut] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_order_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            cents = getattr(data, "total_price_cents", 0)
            items = getattr(data, "items", [])
            return {
                "id": data.id,
                "event_id": data.event_id,
                "order_number": data.order_number,
                "first_name": data.first_name,
                "last_name": data.last_name,
                "email": getattr(data, "email", None),
                "phone": data.phone,
                "street_address": getattr(data, "street_address", None),
                "postal_code": getattr(data, "postal_code", None),
                "city": getattr(data, "city", None),
                "honor_declaration_accepted": data.honor_declaration_accepted,
                "honor_declaration_accepted_at": data.honor_declaration_accepted_at,
                "total_price_cents": cents,
                "total_price": round(cents / 100.0, 2),
                "status": data.status,
                "payment_method": data.payment_method,
                "offline_payment_reference": getattr(data, "offline_payment_reference", None),
                "stripe_payment_intent_id": getattr(data, "stripe_payment_intent_id", None),
                "access_token": data.access_token,
                "cancellation_reason": getattr(data, "cancellation_reason", None),
                "cancellation_comment": getattr(data, "cancellation_comment", None),
                "cancellation_requested_at": getattr(data, "cancellation_requested_at", None),
                "items": items,
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        return data


class PaymentIntentResponse(BaseModel):
    client_secret: str
    publishable_key: str
    payment_intent_id: str
    amount_cents: int
    currency: str = "eur"


class OfflineOrderCreate(BaseModel):
    spot_ids: List[uuid.UUID] = Field(..., min_length=1, description="Liste des IDs de stands à réserver")
    first_name: str = Field(..., min_length=1, max_length=100, description="Prénom de l'exposant")
    last_name: str = Field(..., min_length=1, max_length=100, description="Nom de l'exposant")
    email: Optional[str] = Field(default=None, max_length=255, description="Adresse email facultative")
    phone: str = Field(..., min_length=5, max_length=50, description="Numéro de téléphone")
    street_address: Optional[str] = Field(default=None, max_length=255, description="Adresse postale facultative")
    postal_code: Optional[str] = Field(default=None, max_length=20, description="Code postal facultatif")
    city: Optional[str] = Field(default=None, max_length=100, description="Ville facultative")
    payment_method: Literal["check", "cash", "other"] = Field(
        ...,
        description="Moyen de paiement hors-ligne : check, cash, other",
    )
    offline_payment_reference: Optional[str] = Field(
        default=None, max_length=255, description="Référence ou n° de chèque"
    )
    admin_notes: Optional[str] = Field(
        default=None, max_length=1000, description="Notes administrateur internes"
    )
    custom_price_cents: Optional[int] = Field(
        default=None, ge=0, description="Montant personnalisé en centimes (si omit, calculé d'après les stands)"
    )

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not cleaned:
            return None
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("L'adresse email est invalide.")
        return cleaned

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_non_empty_names(cls, v: str, info) -> str:
        cleaned = v.strip()
        if not cleaned:
            field_name = info.field_name
            label = "Le prénom" if field_name == "first_name" else "Le nom"
            raise ValueError(f"{label} est obligatoire.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        digits_only = re.sub(r"\D", "", cleaned)
        if len(digits_only) < 8 or len(digits_only) > 15:
            raise ValueError("Le numéro de téléphone doit contenir entre 8 et 15 chiffres.")
        return cleaned

    @field_validator("street_address", "postal_code", "city", "offline_payment_reference", "admin_notes")
    @classmethod
    def clean_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None


class EventDashboardStats(BaseModel):
    total_spots: int
    reserved_spots: int
    locked_spots: int
    available_spots: int
    occupancy_rate: float
    total_revenue_cents: int
    total_revenue: float
    stripe_revenue_cents: int
    stripe_revenue: float
    offline_revenue_cents: int
    offline_revenue: float
    offline_check_cents: int = 0
    offline_check_revenue: float = 0.0
    offline_cash_cents: int = 0
    offline_cash_revenue: float = 0.0
    offline_other_cents: int = 0
    offline_other_revenue: float = 0.0
    total_orders_count: int
    confirmed_orders_count: int
    pending_orders_count: int
    offline_orders_count: int
    pending_approval_orders_count: int = 0
    cancellation_requested_orders_count: int = 0


class OrderApprovalAction(BaseModel):
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Motif optionnel du refus ou note d'approbation",
    )


VALID_CANCELLATION_REASONS = {"medical", "personal", "weather", "other"}


class CancellationRequestIn(BaseModel):
    cancellation_reason: str = Field(
        ...,
        max_length=100,
        description="Motif de la demande d'annulation (medical, personal, weather, other)",
    )
    cancellation_comment: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Commentaire explicatif de l'exposant",
    )

    @field_validator("cancellation_reason")
    @classmethod
    def validate_cancellation_reason(cls, v: str) -> str:
        cleaned = (v or "").strip().lower()
        if not cleaned:
            raise ValueError("Le motif d'annulation est obligatoire.")
        if cleaned not in VALID_CANCELLATION_REASONS:
            raise ValueError(
                f"Motif d'annulation invalide. Valeurs acceptées : {', '.join(sorted(VALID_CANCELLATION_REASONS))}."
            )
        return cleaned

    @field_validator("cancellation_comment")
    @classmethod
    def clean_comment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None

    @model_validator(mode="after")
    def validate_other_comment(self) -> "CancellationRequestIn":
        if self.cancellation_reason == "other" and not self.cancellation_comment:
            raise ValueError("Une précision dans le commentaire est obligatoire pour le motif 'autre'.")
        return self


class AdminOrderOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    order_number: str
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str] = None
    phone: str
    street_address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    honor_declaration_accepted: bool = True
    honor_declaration_accepted_at: Optional[datetime] = None
    total_price_cents: int
    total_price: float
    status: str
    payment_method: str
    is_offline: bool = False
    offline_payment_reference: Optional[str] = None
    admin_notes: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    access_token: str
    cancellation_reason: Optional[str] = None
    cancellation_comment: Optional[str] = None
    cancellation_requested_at: Optional[datetime] = None
    items: List[BookingItemOut] = []
    spot_labels: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_admin_order_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            cents = getattr(data, "total_price_cents", 0)
            items = getattr(data, "items", [])
            payment_method = getattr(data, "payment_method", "stripe")
            is_offline = payment_method in ("check", "cash", "other")
            first_name = getattr(data, "first_name", "")
            last_name = getattr(data, "last_name", "")
            full_name = f"{first_name} {last_name}".strip()

            spot_labels = []
            for item in items:
                spot = getattr(item, "spot", None)
                if spot and getattr(spot, "label", None):
                    spot_labels.append(spot.label)

            return {
                "id": data.id,
                "event_id": data.event_id,
                "order_number": data.order_number,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "email": getattr(data, "email", None),
                "phone": getattr(data, "phone", ""),
                "street_address": getattr(data, "street_address", None),
                "postal_code": getattr(data, "postal_code", None),
                "city": getattr(data, "city", None),
                "honor_declaration_accepted": getattr(data, "honor_declaration_accepted", True),
                "honor_declaration_accepted_at": getattr(data, "honor_declaration_accepted_at", None),
                "total_price_cents": cents,
                "total_price": round(cents / 100.0, 2),
                "status": data.status,
                "payment_method": payment_method,
                "is_offline": is_offline,
                "offline_payment_reference": getattr(data, "offline_payment_reference", None),
                "admin_notes": getattr(data, "admin_notes", None),
                "stripe_payment_intent_id": getattr(data, "stripe_payment_intent_id", None),
                "access_token": data.access_token,
                "cancellation_reason": getattr(data, "cancellation_reason", None),
                "cancellation_comment": getattr(data, "cancellation_comment", None),
                "cancellation_requested_at": getattr(data, "cancellation_requested_at", None),
                "items": items,
                "spot_labels": spot_labels,
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        return data


class AdminOrderListResponse(BaseModel):
    items: List[AdminOrderOut]
    total: int
    stats: Optional[EventDashboardStats] = None


