from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.auth.normalization import normalize_email, normalize_phone, normalize_username


def validate_password(value: str) -> str:
    if len(value) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    if not any(character.islower() for character in value):
        raise ValueError("Password must include a lowercase letter.")
    if not any(character.isupper() for character in value):
        raise ValueError("Password must include an uppercase letter.")
    if not any(character.isdigit() for character in value):
        raise ValueError("Password must include a number.")
    if not any(not character.isalnum() for character in value):
        raise ValueError("Password must include a symbol.")
    return value


class RegistrationRequest(BaseModel):
    model_config = ConfigDict()

    full_name: str = Field(min_length=2, max_length=120)
    username: str = Field(default_factory=lambda: f"u_{uuid4().hex[:20]}")
    email: EmailStr
    phone: str | None = None
    phone_region: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    password: str = Field(max_length=1024, repr=False)
    confirm_password: str = Field(max_length=1024, repr=False)
    terms_accepted: bool

    @field_validator("full_name")
    @classmethod
    def full_name_has_content(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter your full name.")
        return value

    @field_validator("username")
    @classmethod
    def username_is_normalized(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def email_is_normalized(cls, value: EmailStr) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def passwords_match_and_terms_are_accepted(self) -> "RegistrationRequest":
        self.phone = normalize_phone(self.phone, self.phone_region)
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        if not self.terms_accepted:
            raise ValueError("You must accept the terms and privacy policy.")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict()

    identifier: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class PasswordResetRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def email_is_normalized(cls, value: EmailStr) -> str:
        return normalize_email(value)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512, repr=False)
    password: str = Field(max_length=1024, repr=False)
    confirm_password: str = Field(max_length=1024, repr=False)

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordResetConfirmRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class EmailVerificationRequest(BaseModel):
    token: str | None = Field(default=None, min_length=32, max_length=512, repr=False)
    email: EmailStr | None = None
    code: str | None = Field(default=None, pattern="^[0-9]{6}$", repr=False)

    @model_validator(mode="after")
    def either_otp_or_legacy_token(self):
        if bool(self.token) == bool(self.email and self.code):
            raise ValueError("Enter your email and six-digit code.")
        return self


class ReauthenticateRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024, repr=False)


class AccountUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = None
    phone_region: str | None = Field(default=None, pattern="^[A-Z]{2}$")

    @model_validator(mode="after")
    def normalize_contact(self):
        self.phone = normalize_phone(self.phone, self.phone_region)
        self.full_name = self.full_name.strip()
        if len(self.full_name) < 2:
            raise ValueError("Enter your full name.")
        return self


class EmailChangeConfirmRequest(BaseModel):
    code: str = Field(pattern="^[0-9]{6}$", repr=False)


class OAuthStartRequest(BaseModel):
    mode: Literal["login", "link", "reauth"] = "login"
    terms_accepted: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024, repr=False)
    password: str = Field(max_length=1024, repr=False)
    confirm_password: str = Field(max_length=1024, repr=False)

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class AccountDeletionRequest(BaseModel):
    password: str | None = Field(default=None, min_length=1, max_length=1024, repr=False)
    confirmation: str | None = None


class PublicUser(BaseModel):
    id: UUID
    full_name: str
    username: str
    email: EmailStr
    phone: str | None
    email_verified: bool
    delivery_id: UUID | None = None
    delivery_status: str | None = None
    verification_expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionSummary(BaseModel):
    id: UUID
    device_type: str | None
    browser: str | None
    operating_system: str | None
    ip_address: str | None
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    status: str
    current: bool


class SecurityEventSummary(BaseModel):
    id: UUID
    event_type: str
    ip_address: str | None
    created_at: datetime
