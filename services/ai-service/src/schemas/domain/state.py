import re
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.schemas.domain.search import ScoredChunk


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
    files: dict[str, str] = Field(default_factory=dict, description="Имя файла -> расшифровка")


class Product(StrEnum):
    orem = "ОРЭМ"
    askue = "АСКУЭ"
    ses = "СЭС"
    losses = "Потери"
    photo_readings = "Фото показаний"


class ConfidenceStatus(StrEnum):
    answered = "answered"
    need_clarification = "need_clarification"
    out_of_scope = "out_of_scope"


class ClientProfile(BaseModel):
    contact_name: str | None = Field(default=None, description="ФИО контактного лица")
    phone: str | None = Field(default=None, description="Телефон в любом формате")
    email: str | None = Field(default=None, description="Электронная почта")
    company_name: str | None = Field(default=None, description="Название организации")

    region: str | None = Field(default=None, description="Регион расположения объекта")
    object_type: str | None = Field(default=None, description="Тип объекта: склад, магазин, завод, СНТ и т.п.")
    power_kw: float | None = Field(default=None, ge=0, description="Присоединённая или нужная мощность, кВт")
    monthly_consumption: float | None = Field(default=None, ge=0, description="Потребление в месяц, кВт·ч")
    voltage_level: str | None = Field(default=None, description="Уровень напряжения, как назвал клиент")

    target_product: Product | None = Field(default=None, description="Какой продукт Energytool нужен клиенту")
    problem_summary: str | None = Field(default=None, description="Задача клиента одной фразой")

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits[0] in "78":
            return "+7" + digits[1:]
        return None

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str | None) -> str | None:
        if value and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()):
            return value.strip().lower()
        return None

    @property
    def has_contacts(self) -> bool:
        return bool(self.contact_name and self.phone and self.company_name)

    def merge(self, newer: "ClientProfile") -> "ClientProfile":
        updates = newer.model_dump(exclude_none=True)
        return self.model_copy(update=updates)


class DialogState(BaseModel):
    session_id: UUID | None = None
    confidence_status: ConfidenceStatus
    is_ready_for_lead: bool = False
    missing_fields: list[str] = Field(
        default_factory=list, description="Имена полей ClientProfile, которых не хватает для расчёта"
    )
    profile: ClientProfile = Field(default_factory=ClientProfile)
    lead_summary: str | None = None


class Timings(BaseModel):
    retrieval_ms: int = 0
    rerank_ms: int = 0
    llm_ms: int = 0
    total_ms: int = 0


class ConsultantReply(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)
    state: DialogState
    chunks: list[ScoredChunk] = Field(default_factory=list)
    timings: Timings = Field(default_factory=Timings)