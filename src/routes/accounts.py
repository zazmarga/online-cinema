from datetime import datetime, timezone
from os.path import exists
from typing import cast

from fastapi import APIRouter, status, BackgroundTasks, Depends, HTTPException
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config.dependencies import (
    get_accounts_email_notificator,
    get_settings,
    get_jwt_auth_manager,
)
from src.config.settings import BaseAppSettings
from src.database.models.accounts import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    RefreshTokenModel,
    PasswordResetTokenModel,
)
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.notifications import EmailSenderInterface

from src.schemas.accounts import (
    UserRegistrationResponseSchema,
    UserRegistrationRequestSchema,
    MessageResponseSchema,
    UserActivationRequestSchema,
    UserActivationRestoreResponseSchema,
    UserActivationRestoreRequestSchema,
    UserLoginResponseSchema,
    UserLoginRequestSchema,
    TokenRefreshResponseSchema,
    TokenRefreshRequestSchema,
    ChangePasswordRequestSchema,
    PasswordResetRequestSchema,
    PasswordResetCompleteRequestSchema,
    UserUpdateRequestSchema,
)
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface
from src.security.passwords import hash_password, verify_password

router = APIRouter()


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    summary="User Registration",
    description="Register a new user with an email and password.",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "description": "Conflict - User with this email already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A user with this email test@example.com already exists."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred during user creation.",
            "content": {
                "application/json": {
                    "example": {"detail": "An error occurred during user creation."}
                }
            },
        },
    },
)
def register_user(
    user_data: UserRegistrationRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> UserRegistrationResponseSchema:
    """
    Endpoint for user registration.

    Registers a new user, hashes their password, and assigns them to the default user group.
    If a user with the same email already exists, an HTTP 409 error is raised.
    In case of any unexpected issues during the creation process, an HTTP 500 error is returned.
    """
    existing_user = db.query(UserModel).filter_by(email=user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail=f"A user with this email {user_data.email} already exists.",
        )

    user_group = db.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()

    # if first time choose user_group
    if not user_group:
        groups = [{"name": group.value} for group in UserGroupEnum]
        db.execute(insert(UserGroupModel).values(groups))
        db.flush()
        user_group = db.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
        db.commit()

    try:
        new_user = UserModel.create(
            email=str(user_data.email),
            raw_password=user_data.password,
            group_id=user_group.id,
        )
        db.add(new_user)
        db.flush()

        activation_token = ActivationTokenModel(user_id=new_user.id)
        db.add(activation_token)
        db.commit()
        db.refresh(new_user)

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="An error occurred during user creation.",
        )
    else:
        activation_link = "http://127.0.0.1/accounts/activate/"

        background_tasks.add_task(
            email_sender.send_activation_email, new_user.email, activation_link
        )

        return UserRegistrationResponseSchema.model_validate(new_user)


@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    summary="Activate User Account",
    description="Activate a user's account using their email and activation token.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The activation token is invalid or expired, "
            "or the user account is already active.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_token": {
                            "summary": "Invalid Token",
                            "value": {"detail": "Invalid or expired activation token."},
                        },
                        "already_active": {
                            "summary": "Account Already Active",
                            "value": {"detail": "User account is already active."},
                        },
                    }
                }
            },
        },
    },
)
def activate_account(
    activation_data: UserActivationRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Endpoint to activate a user's account.

    Verifies the activation token for a user. If valid, activates the account
    and deletes the token. If invalid or expired, raises an appropriate error.
    """
    token_record = (
        db.query(ActivationTokenModel)
        .join(UserModel)
        .filter(
            UserModel.email == activation_data.email,
            ActivationTokenModel.token == activation_data.token,
        )
        .first()
    )

    if not token_record or cast(datetime, token_record.expires_at).replace(
        tzinfo=timezone.utc
    ) < datetime.now(timezone.utc):
        if token_record:
            db.delete(token_record)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token.",
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active.",
        )

    user.is_active = True
    db.delete(token_record)
    db.commit()

    login_link = "http://127.0.0.1/accounts/login/"

    background_tasks.add_task(
        email_sender.send_activation_complete_email,
        str(activation_data.email),
        login_link,
    )

    return MessageResponseSchema(message="User account activated successfully.")


@router.post(
    "/activation-restore/",
    response_model=UserActivationRestoreResponseSchema,
    summary="Restore Activation Token",
    description="Restore an activation token of new user if your activation token is expired.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "Bad Request - User with this email does not exist"
            "or the user account is already active.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_email": {
                            "summary": "Invalid Email",
                            "value": {"detail": "User with this email does not exist."},
                        },
                        "already_active": {
                            "summary": "Account Already Active",
                            "value": {"detail": "User account is already active."},
                        },
                        "token_still_valid": {
                            "summary": "Activation Token Is Still Valid",
                            "value": {
                                "detail": "User's activation token is still valid."
                            },
                        },
                    }
                }
            },
        },
    },
)
def restore_activation_token(
    restore_data: UserActivationRestoreRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> UserActivationRestoreResponseSchema:
    """
    The endpoint to restore an activation token.

    Allow resending a new token if the old one expires.
    """
    user = db.query(UserModel).filter_by(email=restore_data.email).first()
    if not user:
        raise HTTPException(
            status_code=400,
            detail=f"A user with this email {restore_data.email} does not exist.",
        )

    if user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User account is already active.",
        )

    token = (
        db.query(ActivationTokenModel)
        .join(UserModel)
        .filter(
            UserModel.email == restore_data.email,
            ActivationTokenModel.user_id == user.id,
        )
        .first()
    )
    if token:
        if cast(datetime, token.expires_at).replace(tzinfo=timezone.utc) < datetime.now(
            timezone.utc
        ):
            raise HTTPException(
                status_code=400,
                detail="User's activation token is still valid.",
            )
        db.delete(token)
        db.flush()

    try:
        activation_token = ActivationTokenModel(user_id=user.id)
        db.add(activation_token)
        db.commit()
        db.refresh(user)

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="An error occurred during user creation.",
        )

    else:

        activation_link = "http://127.0.0.1/accounts/activate/"

        background_tasks.add_task(
            email_sender.send_activation_restore_email, user.email, activation_link
        )

        return UserActivationRestoreResponseSchema(id=user.id, email=user.email)


@router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
    summary="User Login",
    description="Authenticate a user and return access and refresh tokens.",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {
            "description": "Unauthorized - Invalid email or password.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid email or password."}
                }
            },
        },
        403: {
            "description": "Forbidden - User account is not activated.",
            "content": {
                "application/json": {
                    "example": {"detail": "User account is not activated."}
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred while processing the request.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while processing the request."
                    }
                }
            },
        },
    },
)
def login_user(
    login_data: UserLoginRequestSchema,
    db: Session = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserLoginResponseSchema:
    """
    Endpoint for user login.

    Authenticates a user using their email and password.
    If authentication is successful, creates a new refresh token and
    returns both access and refresh tokens.
    """
    user = cast(
        UserModel, db.query(UserModel).filter_by(email=login_data.email).first()
    )
    if not user or not user.verify_password(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    jwt_refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id,
            days_valid=settings.LOGIN_TIME_DAYS,
            token=jwt_refresh_token,
        )
        db.add(refresh_token)
        db.flush()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )

    jwt_access_token = jwt_manager.create_access_token({"user_id": user.id})
    return UserLoginResponseSchema(
        access_token=jwt_access_token,
        refresh_token=jwt_refresh_token,
    )


@router.post(
    "/logout/",
    summary="User Logout",
    description="Unauthenticate a user and delete user's refresh token.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {"detail": "Authorization header is missing."}
                }
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {"detail": "Authorization header is missing."}
                }
            },
        },
    },
)
def logout_user(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    """
    The endpoint to logout a user.

    On logout, the refresh token is deleted, preventing further use.
    """
    if token:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    else:
        raise HTTPException(status_code=500, detail="Authorization header is missing.")

    if user_id:
        user = db.query(UserModel).join(RefreshTokenModel).filter_by(id=user_id).first()
        try:
            user.is_active = False
            for refresh_token in user.refresh_tokens:
                db.delete(refresh_token)
            db.commit()
            db.refresh(user)
            return
        except AttributeError:
            raise HTTPException(
                status_code=500, detail="Authorization header is missing."
            )


@router.post(
    "/refresh/",
    response_model=TokenRefreshResponseSchema,
    summary="Refresh Access Token",
    description="Refresh the access token using a valid refresh token.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The provided refresh token is invalid or expired.",
            "content": {
                "application/json": {"example": {"detail": "Token has expired."}}
            },
        },
        401: {
            "description": "Unauthorized - Refresh token not found.",
            "content": {
                "application/json": {"example": {"detail": "Refresh token not found."}}
            },
        },
        404: {
            "description": "Not Found - The user associated with the token does not exist.",
            "content": {"application/json": {"example": {"detail": "User not found."}}},
        },
    },
)
def refresh_access_token(
    token_data: TokenRefreshRequestSchema,
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> TokenRefreshResponseSchema:
    """
    Endpoint to refresh an access token.

    Validates the provided refresh token, extracts the user ID from it, and issues
    a new access token. If the token is invalid or expired, an error is returned.
    """
    try:
        decoded_token = jwt_manager.decode_refresh_token(token_data.refresh_token)
        user_id = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    refresh_token_record = (
        db.query(RefreshTokenModel).filter_by(token=token_data.refresh_token).first()
    )
    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    user = db.query(UserModel).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    new_access_token = jwt_manager.create_access_token({"user_id": user_id})

    return TokenRefreshResponseSchema(access_token=new_access_token)


@router.post(
    "/change-password/",
    response_model=MessageResponseSchema,
    summary="Change User Password",
    description="Allows the user to change the password if he knows his current password.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "The new password cannot be the same as the current."
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - Invalid email or password.",
            "content": {
                "application/json": {"example": {"detail": "Invalid password."}}
            },
        },
        403: {
            "description": "Forbidden - User account is not activated.",
            "content": {
                "application/json": {
                    "example": {"detail": "User account is not activated."}
                }
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_token": {
                            "summary": "Missing Token",
                            "value": {"detail": "Authorization header is missing."},
                        },
                        "server_error": {
                            "summary": "Internal Server Error",
                            "value": {
                                "detail": "An error occurred during user's password updating."
                            },
                        },
                    }
                }
            },
        },
    },
)
def change_password(
    change_data: ChangePasswordRequestSchema,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema:
    """
    Endpoint for changing the current password to a new one.

    If user exists and is active, then: if user knows his current password,
    he can change it to a new one.
    """
    if token:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    else:
        raise HTTPException(status_code=500, detail="Authorization header is missing.")

    if change_data.current_password == change_data.new_password:
        raise HTTPException(
            status_code=400,
            detail="The new password cannot be the same as the current.",
        )

    if not verify_password(
        change_data.current_password, hash_password(change_data.current_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )

    user = db.query(UserModel).filter_by(id=user_id).first()
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    try:
        user.password = change_data.new_password
        db.commit()
        db.refresh(user)

        return MessageResponseSchema(message="Password changed successfully.")

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="An error occurred during user's password updating.",
        )


@router.post(
    "/password-reset/request/",
    response_model=MessageResponseSchema,
    summary="Request Password Reset Token",
    description=(
        "Allows a user to request a password reset token. If the user exists and is active, "
        "a new token will be generated and any existing tokens will be invalidated."
    ),
    status_code=status.HTTP_200_OK,
)
def request_password_reset_token(
    data: PasswordResetRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Endpoint to request a password reset token.

    If the user exists and is active, invalidates any existing password reset tokens and generates a new one.
    Always responds with a success message to avoid leaking user information.
    """
    user = db.query(UserModel).filter_by(email=data.email).first()

    if not user or not user.is_active:
        return MessageResponseSchema(
            message="If you are registered, you will receive an email with instructions."
        )

    db.query(PasswordResetTokenModel).filter_by(user_id=user.id).delete()

    reset_token = PasswordResetTokenModel(user_id=cast(int, user.id))
    db.add(reset_token)
    db.commit()

    password_reset_complete_link = "http://127.0.0.1/accounts/password-reset-complete/"

    background_tasks.add_task(
        email_sender.send_password_reset_email,
        str(data.email),
        password_reset_complete_link,
    )

    return MessageResponseSchema(
        message="If you are registered, you will receive an email with instructions."
    )


@router.post(
    "/reset-password/complete/",
    response_model=MessageResponseSchema,
    summary="Reset User Password",
    description="Reset a user's password if a valid token is provided.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The provided email or token is invalid, "
            "the token has expired, or the user account is not active.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_email_or_token": {
                            "summary": "Invalid Email or Token",
                            "value": {"detail": "Invalid email or token."},
                        },
                        "expired_token": {
                            "summary": "Expired Token",
                            "value": {"detail": "Invalid email or token."},
                        },
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred while resetting the password.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while resetting the password."
                    }
                }
            },
        },
    },
)
def reset_password(
    data: PasswordResetCompleteRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Endpoint for resetting a user's password.

    Validates the token and updates the user's password if the token is valid and not expired.
    Deletes the token after successful password reset.
    """
    user = db.query(UserModel).filter_by(email=data.email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token."
        )

    token_record = db.query(PasswordResetTokenModel).filter_by(user_id=user.id).first()

    expires_at = cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc)

    if (
        not token_record
        or token_record.token != data.token
        or expires_at < datetime.now(timezone.utc)
    ):
        if token_record:
            db.delete(token_record)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token."
        )

    try:
        user.password = data.password
        db.delete(token_record)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password.",
        )

    login_link = "http://127.0.0.1/accounts/login/"

    background_tasks.add_task(
        email_sender.send_password_reset_complete_email, str(data.email), login_link
    )

    return MessageResponseSchema(message="Password reset successfully.")


@router.patch(
    "/update-user/{user_id}/",
    response_model=MessageResponseSchema,
    summary="Change User Group OR User Is_active Manually",
    description="Change the user's group or is_active manually, allowed only by admins.",
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authorization header is missing or Invalid token."
                    }
                }
            },
        },
        403: {
            "description": "Forbidden.",
            "content": {
                "application/json": {
                    "example": {"detail": "Forbidden, allowed only by admins."}
                }
            },
        },
        404: {
            "description": "User not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "User with the given ID was not found."}
                }
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {"detail": "An error occurred while updating the user."}
                }
            },
        },
    },
)
def update_user(
    user_id: int,
    data: UserUpdateRequestSchema,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema:
    """
    Endpoint for update user: change the user's group or change is_active manually.
    Allowed only by admins.

    Steps:
    - Validate received user_id
    - Validate current user access token.
    - Check if the current user is ADMIN.
    - Change the user's group or is_active manually.
    """
    user = db.query(UserModel).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with the given ID was not found.",
        )

    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    current_user = db.query(UserModel).filter_by(id=current_user_id).first()
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden, allowed only by admins.",
        )
    try:
        if data.group and data.group != user.group.name:
            new_group = db.query(UserGroupModel).filter_by(name=data.group).first()
            if not new_group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Group with the given name was not found.",
                )
            user.group_id = new_group.id
        if exists(data.is_active) and data.is_active != user.is_active:
            user.is_active = data.is_active
        db.add(user)
        db.commit()
        db.refresh(user)

        return MessageResponseSchema(message="User updated successfully.")

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the user.",
        )
