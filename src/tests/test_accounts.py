from datetime import timezone, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.database.models import UserModel
from src.database.models.accounts import (
    ActivationTokenModel,
    UserGroupModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserGroupEnum,
)


def test_register_user_success(client, db_session, seed_user_groups):
    """
    Test successful user registration.

    Validates that a new user and an activation token are created in the database.
    """
    payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}

    response = client.post("/api/v1/accounts/register/", json=payload)

    assert response.status_code == 201, "Expected status code 201 Created."
    response_data = response.json()
    assert response_data["email"] == payload["email"], "Returned email does not match."
    assert "id" in response_data, "Response does not contain user ID."

    created_user = db_session.query(UserModel).filter_by(email=payload["email"]).first()
    assert created_user is not None, "User was not created in the database."
    assert (
        created_user.email == payload["email"]
    ), "Created user's email does not match."

    activation_token = (
        db_session.query(ActivationTokenModel)
        .filter_by(user_id=created_user.id)
        .first()
    )
    assert (
        activation_token is not None
    ), "Activation token was not created in the database."
    assert (
        activation_token.user_id == created_user.id
    ), "Activation token's user_id does not match."
    assert activation_token.token is not None, "Activation token has no token value."

    expires_at = activation_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(
        timezone.utc
    ), "Activation token is already expired."


@pytest.mark.parametrize(
    "invalid_password, expected_error",
    [
        ("short", "Password must contain at least 8 characters."),
        ("NoDigitHere!", "Password must contain at least one digit."),
        ("nodigitnorupper@", "Password must contain at least one uppercase letter."),
        ("NOLOWERCASE1@", "Password must contain at least one lower letter."),
        (
            "NoSpecial123",
            "Password must contain at least one special character: @, $, !, %, *, ?, #, &.",
        ),
    ],
)
def test_register_user_password_validation(
    client, seed_user_groups, invalid_password, expected_error
):
    """
    Test password strength validation in the user registration endpoint.

    Ensures the endpoint returns the correct error for invalid passwords.
    """
    payload = {"email": "testuser@example.com", "password": invalid_password}

    response = client.post("/api/v1/accounts/register/", json=payload)

    assert response.status_code == 422, "Expected status code 422 for invalid input."

    response_data = response.json()
    assert expected_error in str(
        response_data
    ), f"Expected error message: {expected_error}"


def test_register_user_conflict(client, db_session, seed_user_groups):
    """
    Test user registration conflict.

    Ensures that trying to register a user with an existing email
    returns a 409 Conflict status and the correct error message.
    """
    payload = {"email": "conflictuser@example.com", "password": "StrongPassword123!"}

    response_first = client.post("/api/v1/accounts/register/", json=payload)
    assert (
        response_first.status_code == 201
    ), "Expected status code 201 for the first registration."

    created_user = db_session.query(UserModel).filter_by(email=payload["email"]).first()
    assert (
        created_user is not None
    ), "User should be created after the first registration."

    response_second = client.post("/api/v1/accounts/register/", json=payload)
    assert (
        response_second.status_code == 409
    ), "Expected status code 409 for a duplicate registration."

    response_data = response_second.json()
    expected_message = f"A user with this email {payload['email']} already exists."
    assert (
        response_data["detail"] == expected_message
    ), f"Expected error message: {expected_message}"


# def test_register_user_internal_server_error(client, seed_user_groups):
#     """
#     Test server error during user registration.
#
#     Ensures that a 500 Internal Server Error is returned when a database operation fails.
#     """
#     payload = {"email": "erroruser@example.com", "password": "StrongPassword123!"}
#
#     with patch("routes.accounts.Session.commit", side_effect=SQLAlchemyError):
#         response = client.post("/api/v1/accounts/register/", json=payload)
#
#         assert (
#             response.status_code == 500
#         ), "Expected status code 500 for internal server error."
#
#         response_data = response.json()
#         expected_message = "An error occurred during user creation."
#         assert (
#             response_data["detail"] == expected_message
#         ), f"Expected error message: {expected_message}"


def test_activate_account_success(client, db_session, seed_user_groups):
    """
    Test successful activation of a user account.

    Steps:
    - Register a new user.
    - Verify the user is inactive.
    - Activate the user using the activation token.
    - Verify the user is activated and the token is deleted.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }

    registration_response = client.post(
        "/api/v1/accounts/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    assert user is not None, "User was not created in the database."
    assert not user.is_active, "Newly registered user should not be active."

    assert (
        user.activation_token.token is not None
    ), "Activation token was not created in the database."

    activation_payload = {
        "email": registration_payload["email"],
        "token": user.activation_token.token,
    }

    activation_response = client.post(
        "/api/v1/accounts/activate/", json=activation_payload
    )
    assert (
        activation_response.status_code == 200
    ), "Expected status code 200 for successful activation."
    assert (
        activation_response.json()["message"] == "User account activated successfully."
    )

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    db_session.refresh(user)
    assert user.is_active, "User should be active after successful activation."

    token = db_session.query(ActivationTokenModel).filter_by(user_id=user.id).first()
    assert (
        token is None
    ), "Activation token should be deleted after successful activation."


def test_activate_user_with_expired_token(client, db_session, seed_user_groups):
    """
    Test activation with an expired token.

    Ensures that the endpoint returns a 400 error when the activation token is expired.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = client.post(
        "/api/v1/accounts/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    assert user is not None, "User should exist in the database."
    assert not user.is_active, "User should not be active before activation."

    activation_token = (
        db_session.query(ActivationTokenModel).filter_by(user_id=user.id).first()
    )
    assert activation_token is not None, "Activation token should exist for the user."
    activation_token.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.commit()

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token,
    }
    activation_response = client.post(
        "/api/v1/accounts/activate/", json=activation_payload
    )

    assert (
        activation_response.status_code == 400
    ), "Expected status code 400 for expired token."
    assert (
        activation_response.json()["detail"] == "Invalid or expired activation token."
    ), "Expected error message for expired token."


def test_activate_user_with_deleted_token(client, db_session, seed_user_groups):
    """
    Test activation with a deleted token.

    Ensures that the endpoint returns a 400 error when the activation token is deleted.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = client.post(
        "/api/v1/accounts/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    assert user is not None, "User should exist in the database."
    assert not user.is_active, "User should not be active before activation."

    activation_token = (
        db_session.query(ActivationTokenModel).filter_by(user_id=user.id).first()
    )
    assert activation_token is not None, "Activation token should exist for the user."
    db_session.delete(activation_token)
    db_session.commit()

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token,
    }
    activation_response = client.post(
        "/api/v1/accounts/activate/", json=activation_payload
    )

    assert (
        activation_response.status_code == 400
    ), "Expected status code 400 for deleted token."
    assert (
        activation_response.json()["detail"] == "Invalid or expired activation token."
    ), "Expected error message for deleted token."


def test_activate_already_active_user(client, db_session, seed_user_groups):
    """
    Test activation of an already active user.

    Ensures that the endpoint returns a 400 error if the user is already active.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = client.post(
        "/api/v1/accounts/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    assert user is not None, "User should exist in the database."

    user.is_active = True
    db_session.commit()

    activation_token = (
        db_session.query(ActivationTokenModel).filter_by(user_id=user.id).first()
    )
    assert activation_token is not None, "Activation token should exist for the user."

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token,
    }
    activation_response = client.post(
        "/api/v1/accounts/activate/", json=activation_payload
    )

    assert (
        activation_response.status_code == 400
    ), "Expected status code 400 for already active user."
    assert (
        activation_response.json()["detail"] == "User account is already active."
    ), "Expected error message for already active user."


def test_request_password_reset_token_success(client, db_session, seed_user_groups):
    """
    Test successful password reset token request.

    Ensures that a password reset token is created for an active user.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = client.post(
        "/api/v1/accounts/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    assert user is not None, "User should exist in the database."

    user.is_active = True
    db_session.commit()

    reset_payload = {"email": registration_payload["email"]}
    reset_response = client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_payload
    )

    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for successful token request."
    assert (
        reset_response.json()["message"]
        == "If you are registered, you will receive an email with instructions."
    ), "Expected success message for password reset token request."

    reset_token = (
        db_session.query(PasswordResetTokenModel).filter_by(user_id=user.id).first()
    )
    assert (
        reset_token is not None
    ), "Password reset token should be created for the user."

    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(
        timezone.utc
    ), "Password reset token should have a future expiration date."


def test_request_password_reset_token_nonexistent_user(client, db_session):
    """
    Test password reset token request for a non-existent user.

    Ensures that the response is correct and no password reset token is created.
    """
    reset_payload = {"email": "nonexistent@example.com"}

    reset_response = client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_payload
    )

    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for non-existent user request."
    assert (
        reset_response.json()["message"]
        == "If you are registered, you will receive an email with instructions."
    ), "Expected generic success message for non-existent user request."

    reset_token_count = db_session.query(PasswordResetTokenModel).count()
    assert (
        reset_token_count == 0
    ), "No password reset token should be created for non-existent user."


def test_request_password_reset_token_for_inactive_user(
    client, db_session, seed_user_groups
):
    """
    Test password reset token request for a registered but inactive user.

    Ensures that the response is correct and no password reset token is created.
    """
    registration_payload = {
        "email": "inactiveuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = client.post(
        "/api/v1/accounts/register/", json=registration_payload
    )

    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    created_user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    assert created_user is not None, "User should be created in the database."
    assert not created_user.is_active, "User should not be active after registration."

    reset_payload = {"email": registration_payload["email"]}
    reset_response = client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_payload
    )

    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for inactive user password reset request."
    assert (
        reset_response.json()["message"]
        == "If you are registered, you will receive an email with instructions."
    ), "Expected generic success message for inactive user password reset request."

    reset_token_count = db_session.query(PasswordResetTokenModel).count()
    assert (
        reset_token_count == 0
    ), "No password reset token should be created for an inactive user."


def test_reset_password_success(client, db_session, seed_user_groups):
    """
    Test the complete password reset flow.

    - Register a user.
    - Activate the user.
    - Request a password reset token.
    - Use the token to reset the password.
    - Verify the password is updated in the database.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "OldPassword123!",
    }
    registration_response = client.post(
        "/api/v1/accounts/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    created_user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    assert created_user is not None, "User should be created in the database."
    activation_token = (
        db_session.query(ActivationTokenModel)
        .filter_by(user_id=created_user.id)
        .first()
    )
    assert (
        activation_token is not None
    ), "Activation token should be created in the database."

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token,
    }
    activation_response = client.post(
        "/api/v1/accounts/activate/", json=activation_payload
    )
    assert (
        activation_response.status_code == 200
    ), "Expected status code 200 for successful activation."

    db_session.refresh(created_user)
    assert created_user.is_active, "User should be active after successful activation."

    reset_request_payload = {"email": registration_payload["email"]}
    reset_request_response = client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_request_payload
    )
    assert (
        reset_request_response.status_code == 200
    ), "Expected status code 200 for password reset token request."

    reset_token_record = (
        db_session.query(PasswordResetTokenModel)
        .filter_by(user_id=created_user.id)
        .first()
    )
    assert (
        reset_token_record is not None
    ), "Password reset token should be created in the database."

    new_password = "NewSecurePassword123!"
    reset_payload = {
        "email": registration_payload["email"],
        "token": reset_token_record.token,
        "password": new_password,
    }
    reset_response = client.post(
        "/api/v1/accounts/reset-password/complete/", json=reset_payload
    )
    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for successful password reset."
    assert reset_response.json()["message"] == "Password reset successfully."

    db_session.refresh(created_user)
    assert created_user.verify_password(
        new_password
    ), "Password should be updated successfully in the database."


def test_reset_password_invalid_email(client, db_session):
    """
    Test password reset with an email that does not exist in the database.

    Validates that the endpoint returns a 400 status code and appropriate error message.
    """
    reset_payload = {
        "email": "nonexistent@example.com",
        "token": "random_token",
        "password": "NewSecurePassword123!",
    }

    response = client.post(
        "/api/v1/accounts/reset-password/complete/", json=reset_payload
    )

    assert response.status_code == 400, "Expected status code 400 for invalid email."
    assert (
        response.json()["detail"] == "Invalid email or token."
    ), "Unexpected error message."


def test_reset_password_invalid_token(client, db_session, seed_user_groups):
    """
    Test password reset with an incorrect token.

    Validates that the endpoint returns a 400 status code and appropriate error message.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/api/v1/accounts/register/", json=registration_payload)
    assert response.status_code == 201, "User registration failed."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    user.is_active = True
    db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    response = client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_request_payload
    )
    assert response.status_code == 200, "Password reset request failed."

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": "incorrect_token",
        "password": "NewSecurePassword123!",
    }
    response = client.post(
        "/api/v1/accounts/reset-password/complete/", json=reset_complete_payload
    )

    assert response.status_code == 400, "Expected status code 400 for invalid token."
    assert (
        response.json()["detail"] == "Invalid email or token."
    ), "Unexpected error message."

    token_record = (
        db_session.query(PasswordResetTokenModel).filter_by(user_id=user.id).first()
    )
    assert token_record is None, "Invalid token was not removed."


def test_reset_password_expired_token(client, db_session, seed_user_groups):
    """
    Test password reset with an expired token.

    Validates that the endpoint returns a 400 status code and appropriate error message.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/api/v1/accounts/register/", json=registration_payload)
    assert response.status_code == 201, "User registration failed."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    user.is_active = True
    db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    response = client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_request_payload
    )
    assert response.status_code == 200, "Password reset request failed."

    token_record = (
        db_session.query(PasswordResetTokenModel).filter_by(user_id=user.id).first()
    )
    assert token_record is not None, "Password reset token not created."
    token_record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": token_record.token,
        "password": "NewSecurePassword123!",
    }
    response = client.post(
        "/api/v1/accounts/reset-password/complete/", json=reset_complete_payload
    )

    assert response.status_code == 400, "Expected status code 400 for expired token."
    assert (
        response.json()["detail"] == "Invalid email or token."
    ), "Unexpected error message."

    expired_token = (
        db_session.query(PasswordResetTokenModel).filter_by(user_id=user.id).first()
    )
    assert expired_token is None, "Expired token was not removed."


def test_reset_password_sqlalchemy_error(client, db_session, seed_user_groups):
    """
    Test password reset when a database commit raises SQLAlchemyError.

    Validates that the endpoint returns a 500 status code and appropriate error message.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/api/v1/accounts/register/", json=registration_payload)
    assert response.status_code == 201, "User registration failed."

    user = (
        db_session.query(UserModel)
        .filter_by(email=registration_payload["email"])
        .first()
    )
    user.is_active = True
    db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    response = client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_request_payload
    )
    assert response.status_code == 200, "Password reset request failed."

    token_record = (
        db_session.query(PasswordResetTokenModel).filter_by(user_id=user.id).first()
    )
    assert token_record is not None, "Password reset token not created."

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": token_record.token,
        "password": "NewSecurePassword123!",
    }

    with patch("routes.accounts.Session.commit", side_effect=SQLAlchemyError):
        response = client.post(
            "/api/v1/accounts/reset-password/complete/", json=reset_complete_payload
        )

    assert response.status_code == 500, "Expected status code 500 for SQLAlchemyError."
    assert (
        response.json()["detail"] == "An error occurred while resetting the password."
    ), "Unexpected error message for SQLAlchemyError."


def test_login_user_success(client, db_session, jwt_manager, seed_user_groups):
    """
    Test successful login.

    Validates that access and refresh tokens are returned, refresh token is stored in the database,
    and both tokens are valid.
    """
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }
    response = client.post("/api/v1/accounts/login/", json=login_payload)

    assert response.status_code == 201, "Expected status code 201 for successful login."
    response_data = response.json()
    assert "access_token" in response_data, "Access token is missing in the response."
    assert "refresh_token" in response_data, "Refresh token is missing in the response."
    assert response_data["access_token"], "Access token is empty."
    assert response_data["refresh_token"], "Refresh token is empty."

    access_token_data = jwt_manager.decode_access_token(response_data["access_token"])
    assert (
        access_token_data["user_id"] == user.id
    ), "Access token does not contain correct user ID."

    refresh_token_data = jwt_manager.decode_refresh_token(
        response_data["refresh_token"]
    )
    assert (
        refresh_token_data["user_id"] == user.id
    ), "Refresh token does not contain correct user ID."

    refresh_token_record = (
        db_session.query(RefreshTokenModel).filter_by(user_id=user.id).first()
    )
    assert (
        refresh_token_record is not None
    ), "Refresh token was not stored in the database."
    assert (
        refresh_token_record.token == response_data["refresh_token"]
    ), "Stored refresh token does not match."

    expires_at = refresh_token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(timezone.utc), "Refresh token is already expired."


def test_login_user_invalid_cases(client, db_session, seed_user_groups):
    """
    Test login with invalid cases:
    1. Non-existent user.
    2. Incorrect password for an existing user.
    """
    login_payload = {"email": "nonexistent@example.com", "password": "SomePassword123!"}
    response = client.post("/api/v1/accounts/login/", json=login_payload)

    assert (
        response.status_code == 401
    ), "Expected status code 401 for non-existent user."
    assert (
        response.json()["detail"] == "Invalid email or password."
    ), "Unexpected error message for non-existent user."

    user_payload = {"email": "testuser@example.com", "password": "CorrectPassword123!"}
    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    login_payload_incorrect_password = {
        "email": user_payload["email"],
        "password": "WrongPassword123!",
    }
    response = client.post(
        "/api/v1/accounts/login/", json=login_payload_incorrect_password
    )

    assert (
        response.status_code == 401
    ), "Expected status code 401 for incorrect password."
    assert (
        response.json()["detail"] == "Invalid email or password."
    ), "Unexpected error message for incorrect password."


def test_login_user_inactive_account(client, db_session, seed_user_groups):
    """
    Test login with an inactive user account.

    Validates that the endpoint returns a 403 status code and an appropriate error message.
    """
    user_payload = {
        "email": "inactiveuser@example.com",
        "password": "StrongPassword123!",
    }
    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = False
    db_session.add(user)
    db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }
    response = client.post("/api/v1/accounts/login/", json=login_payload)

    assert response.status_code == 403, "Expected status code 403 for inactive user."
    assert (
        response.json()["detail"] == "User account is not activated."
    ), "Unexpected error message for inactive user."


def test_login_user_commit_error(client, db_session, seed_user_groups):
    """
    Test login when a database commit error occurs.

    Validates that the endpoint returns a 500 status code and an appropriate error message.
    """
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }

    with patch("routes.accounts.Session.commit", side_effect=SQLAlchemyError):
        response = client.post("/api/v1/accounts/login/", json=login_payload)

    assert (
        response.status_code == 500
    ), "Expected status code 500 for database commit error."
    assert (
        response.json()["detail"] == "An error occurred while processing the request."
    ), "Unexpected error message for database commit error."


def test_refresh_access_token_success(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test successful access token refresh.

    Validates that a new access token is returned when a valid refresh token is provided.
    """
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }
    login_response = client.post("/api/v1/accounts/login/", json=login_payload)
    assert (
        login_response.status_code == 201
    ), "Expected status code 201 for successful login."
    login_data = login_response.json()
    refresh_token = login_data["refresh_token"]

    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = client.post("/api/v1/accounts/refresh/", json=refresh_payload)

    assert (
        refresh_response.status_code == 200
    ), "Expected status code 200 for successful token refresh."
    refresh_data = refresh_response.json()
    assert "access_token" in refresh_data, "Access token is missing in the response."
    assert refresh_data["access_token"], "Access token is empty."

    access_token_data = jwt_manager.decode_access_token(refresh_data["access_token"])
    assert (
        access_token_data["user_id"] == user.id
    ), "Access token does not contain correct user ID."


def test_refresh_access_token_expired_token(client, jwt_manager):
    """
    Test refresh token with expired token.

    Validates that a 400 status code and 'Token has expired.' message are returned
    when the refresh token is expired.
    """
    expired_token = jwt_manager.create_refresh_token(
        {"user_id": 1}, expires_delta=timedelta(days=-1)
    )

    refresh_payload = {"refresh_token": expired_token}
    refresh_response = client.post("/api/v1/accounts/refresh/", json=refresh_payload)

    assert (
        refresh_response.status_code == 400
    ), "Expected status code 400 for expired token."
    assert (
        refresh_response.json()["detail"] == "Token has expired."
    ), "Unexpected error message."


def test_refresh_access_token_token_not_found(client, jwt_manager):
    """
    Test refresh token when token is not found in the database.

    Validates that a 401 status code and 'Refresh token not found.' message
    are returned when the refresh token is not stored in the database.
    """
    refresh_token = jwt_manager.create_refresh_token({"user_id": 1})

    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = client.post("/api/v1/accounts/refresh/", json=refresh_payload)

    assert (
        refresh_response.status_code == 401
    ), "Expected status code 401 for token not found."
    assert (
        refresh_response.json()["detail"] == "Refresh token not found."
    ), "Unexpected error message."


def test_refresh_access_token_user_not_found(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test refresh token when user ID inside the token does not exist in the database.

    Validates that a 404 status code and 'User not found.' message
    are returned when the user ID in the token is invalid.
    """
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    invalid_user_id = 9999
    refresh_token = jwt_manager.create_refresh_token({"user_id": invalid_user_id})

    refresh_token_record = RefreshTokenModel.create(
        user_id=invalid_user_id, days_valid=7, token=refresh_token
    )
    db_session.add(refresh_token_record)
    db_session.commit()

    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = client.post("/api/v1/accounts/refresh/", json=refresh_payload)

    assert (
        refresh_response.status_code == 404
    ), "Expected status code 404 for non-existent user."
    assert (
        refresh_response.json()["detail"] == "User not found."
    ), "Unexpected error message."


def test_restore_activation_success(client, db_session, seed_user_groups):
    """
    Test successful of restore an activation token of new user if activation token is expired.

     Validates that a new activation token are created in the database.
    """
    payload = {"email": "testuser@example.com"}

    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )
    user = UserModel.create(
        email=payload["email"],
        raw_password="StrongPassword123!",
        group_id=user_group.id,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/api/v1/accounts/activation-restore/", json=payload)
    new_activation_token = user.activation_token
    assert response.status_code == 201, "Expected status code 201 Created."
    response_data = response.json()
    assert response_data["email"] == payload["email"], "Returned email does not match."
    assert "id" in response_data, "Response does not contain user ID."

    assert (
        new_activation_token is not None
    ), "Activation token was not created in the database."
    assert (
        new_activation_token.user_id == user.id
    ), "Activation token's user_id does not match."

    assert (
        new_activation_token.token is not None
    ), "Activation token has no token value."


def test_restore_activation_email_not_exist(client, db_session):
    """
    Test of restore an activation token if email not exist in the database.

    """
    payload = {"email": "testuser@example.com"}

    response = client.post("/api/v1/accounts/activation-restore/", json=payload)

    assert response.status_code == 400, "Expected status code 400 Bad Request."

    response_data = response.json()
    assert (
        response_data["detail"]
        == f"A user with this email {payload['email']} does not exist."
    ), "Unexpected error message."


def test_restore_activation_user_already_active(client, db_session, seed_user_groups):
    """
    Test of restore an activation token if user is already active.

    """
    payload = {"email": "testuser@example.com"}

    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )
    user = UserModel.create(
        email=payload["email"],
        raw_password="StrongPassword123!",
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    response = client.post("/api/v1/accounts/activation-restore/", json=payload)

    assert response.status_code == 400, "Expected status code 400 Bad Request."

    response_data = response.json()
    assert (
        response_data["detail"] == "User account is already active."
    ), "Unexpected error message."


def test_logout_user_successfully(client, jwt_manager, db_session, seed_user_groups):
    """
    Test of logout of a user.

    Validates that a user's refresh token is deleted from the database.
    """
    response = client.post("/api/v1/accounts/logout/", headers={"Authorization": ""})
    assert response.status_code == 401, "Expected status code 401 Unauthorized."

    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )
    user = UserModel.create(
        email="testuser@example.com",
        raw_password="StrongPassword123!",
        group_id=user_group.id,
    )
    db_session.add(user)
    db_session.flush()

    user.is_active = True
    refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    refresh_token_record = RefreshTokenModel.create(
        user_id=user.id, days_valid=7, token=refresh_token
    )
    db_session.add(refresh_token_record)
    db_session.commit()

    assert (
        user.refresh_tokens != []
    ), "Before logging out user must have at least one refresh token."

    access_token = jwt_manager.create_access_token({"user_id": user.id})
    response = client.post(
        "/api/v1/accounts/logout/", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 204, "Expected status code 204."

    assert (
        user.refresh_tokens == []
    ), "After logging out, the user should not have a refresh token."


def test_change_password_with_current_password(
    client, jwt_manager, db_session, seed_user_groups
):
    """
    Test of changing user password if user knows his current password.

    """
    payload = {
        "current_password": "StrongPassword123!",
        "new_password": "NewStrongPassword123!",
    }

    response = client.post(
        "/api/v1/accounts/change-password/", headers={"Authorization": ""}, json=payload
    )
    assert response.status_code == 401, "Expected status code 401 Unauthorized."

    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )
    user = UserModel.create(
        email="testuser@example.com",
        raw_password="StrongPassword123!",
        group_id=user_group.id,
    )
    db_session.add(user)
    db_session.commit()

    access_token = jwt_manager.create_access_token({"user_id": user.id})
    response = client.post(
        "/api/v1/accounts/change-password/",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    assert response.status_code == 403, "Expected status code 403 Forbidden."

    user.is_active = True
    response = client.post(
        "/api/v1/accounts/change-password/",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    assert response.status_code == 200, "Expected status code 200 OK."


def test_change_user_group_or_user_is_active_manually(
    client, jwt_manager, db_session, seed_user_groups
):
    """
    Test of changing user group or user is active manually.

    Validates that this endpoint allowed only for user-admins & changes successfully.
    """
    user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.ADMIN).first()
    )
    admin_user = UserModel.create(
        email="admin@example.com",
        raw_password="AdminStrongPassword123!",
        group_id=user_group.id,
    )
    db_session.add(admin_user)
    db_session.flush()
    admin_user.is_active = True

    other_user_group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.USER).first()
    )
    other_user = UserModel.create(
        email="user@example.com",
        raw_password="userStrongPassword123!",
        group_id=other_user_group.id,
    )
    db_session.add(other_user)
    db_session.flush()
    other_user.is_active = True
    db_session.commit()

    payload = {"is_active": False, "group": "moderator"}

    access_token_other = jwt_manager.create_access_token({"user_id": other_user.id})

    response = client.patch(
        f"/api/v1/accounts/update-user/{other_user.id}/",
        headers={"Authorization": f"Bearer {access_token_other}"},
        json=payload,
    )
    assert response.status_code == 403, "Expected status code 403 Forbidden."
    response_data = response.json()
    assert (
        response_data["detail"] == "Forbidden, allowed only by admins."
    ), "Unexpected error message."

    access_token_admin = jwt_manager.create_access_token({"user_id": admin_user.id})

    response = client.patch(
        f"/api/v1/accounts/update-user/{other_user.id}/",
        headers={"Authorization": f"Bearer {access_token_admin}"},
        json=payload,
    )
    assert response.status_code == 200, "Expected status code 200 OK."
    response_data = response.json()
    assert (
        response_data["message"] == "User updated successfully."
    ), "Unexpected error message."

    assert (
        other_user.group.name == UserGroupEnum.MODERATOR
    ), "The user's group should have changed from USER to MODERATOR."

    assert (
        other_user.is_active == False
    ), "The user's is_active should have changed to False."

    payload = {"group": "group"}
    response = client.patch(
        f"/api/v1/accounts/update-user/{other_user.id}/",
        headers={"Authorization": f"Bearer {access_token_admin}"},
        json=payload,
    )
    assert response.status_code == 422, "Expected status code 422."
    response_data = response.json()
    assert (
        response_data["detail"][0]["msg"]
        == "Input should be 'user', 'moderator' or 'admin'"
    ), "Unexpected error message."

    payload = {"group": "admin"}
    response = client.patch(
        f"/api/v1/accounts/update-user/999/",
        headers={"Authorization": f"Bearer {access_token_admin}"},
        json=payload,
    )
    assert response.status_code == 404, "Expected status code 404 Not Found."
    response_data = response.json()
    assert (
        response_data["detail"] == "User with the given ID was not found."
    ), "Unexpected error message."
