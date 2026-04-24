from pydantic import BaseModel
from typing import Optional


class UserResponse(BaseModel):
    phone_number: str
    full_name: Optional[str] = None
    username: Optional[str] = None
    language: str
    unique_code: str
    dashboard_url: str

    model_config = {"from_attributes": True}


class BotRegisterRequest(BaseModel):
    telegram_id: int
    phone_number: str
    full_name: Optional[str] = None
    username: Optional[str] = None
    language: str = "en"


class BotRegisterResponse(BaseModel):
    unique_code: str
    dashboard_url: str
    is_new_user: bool
    is_registered: bool
