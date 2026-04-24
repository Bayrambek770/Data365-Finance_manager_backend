from pydantic import BaseModel, field_validator
from typing import Optional, List
import datetime as dt
import uuid


class TransactionCreate(BaseModel):
    amount: float
    currency: str = "UZS"
    type: str
    category_id: uuid.UUID
    date: Optional[dt.date] = None
    note: Optional[str] = None
    source: str = "dashboard"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v not in ("UZS", "USD"):
            raise ValueError("Currency must be UZS or USD")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("income", "expense"):
            raise ValueError("Type must be income or expense")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[dt.date]) -> Optional[dt.date]:
        if v and v > dt.date.today():
            raise ValueError("Transaction date cannot be in the future")
        return v



class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    type: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    date: Optional[dt.date] = None
    note: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("UZS", "USD"):
            raise ValueError("Currency must be UZS or USD")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("income", "expense"):
            raise ValueError("Type must be income or expense")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[dt.date]) -> Optional[dt.date]:
        if v and v > dt.date.today():
            raise ValueError("Transaction date cannot be in the future")
        return v


class BudgetWarning(BaseModel):
    category: str
    limit: float
    current_spend: float
    exceeded_by: float
    percentage_used: float
    status: str


class TransactionItem(BaseModel):
    id: uuid.UUID
    date: dt.date
    category_id: uuid.UUID
    category_name: str
    category_type: str
    note: Optional[str] = None
    amount: float
    currency: str
    type: str
    source: str
    added_by_phone: str
    is_mine: bool
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: uuid.UUID
    date: dt.date
    category_id: uuid.UUID
    category_name: str
    note: Optional[str] = None
    amount: float
    currency: str
    type: str
    source: str
    budget_warning: Optional[BudgetWarning] = None

    model_config = {"from_attributes": True}


class PaginatedTransactions(BaseModel):
    items: List[TransactionItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class BotTransactionCreate(BaseModel):
    telegram_id: int
    amount: float
    currency: str = "UZS"
    type: str
    category_id: uuid.UUID
    date: Optional[dt.date] = None
    note: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v not in ("UZS", "USD"):
            raise ValueError("Currency must be UZS or USD")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("income", "expense"):
            raise ValueError("Type must be income or expense")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[dt.date]) -> Optional[dt.date]:
        if v and v > dt.date.today():
            raise ValueError("Transaction date cannot be in the future")
        return v
