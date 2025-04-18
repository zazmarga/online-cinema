from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from src.database.models.accounts import UserGroupEnum
from src.database.validators.accounts import validate_password_strength


class BaseEmailPasswordSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = {"from_attributes": True}

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)


class UserRegistrationRequestSchema(BaseEmailPasswordSchema):
    pass


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}


class MessageResponseSchema(BaseModel):
    message: str


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class UserActivationRestoreResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}


class UserActivationRestoreRequestSchema(BaseModel):
    email: EmailStr

    model_config = {"from_attributes": True}


class UserLoginResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserLoginRequestSchema(BaseEmailPasswordSchema):
    pass


class TokenRefreshResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class ChangePasswordRequestSchema(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequestSchema(BaseEmailPasswordSchema):
    token: str


class UserUpdateRequestSchema(BaseModel):
    group: Optional[UserGroupEnum] = None
    is_active: Optional[bool] = None

    @field_validator("group")
    @classmethod
    def validate_group(cls, value):
        return value.lower()

    model_config = {"from_attributes": True}
