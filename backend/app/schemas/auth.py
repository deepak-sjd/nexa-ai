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
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


# A resized profile photo sent as a data URL (~110 KB max).
_AVATAR = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    # "" removes the photo; omit the field to leave it unchanged.
    avatar: str | None = Field(default=None, max_length=150_000)

    @field_validator("avatar")
    @classmethod
    def _check_avatar(cls, value):
        if value and not _AVATAR.match(value):
            raise ValueError("Profile photo must be a PNG, JPEG or WebP image.")

        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser
