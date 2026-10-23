import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value: str) -> str:
    value = value.strip().lower()

    if not _EMAIL.match(value):
        raise ValueError("Enter a valid email address.")

    return value


class RegisterRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)

    _check_email = field_validator("email")(_clean_email)


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)

    _check_email = field_validator("email")(_clean_email)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=10, max_length=4096)


class AuthUser(BaseModel):
    id: int
    email: str
    name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser