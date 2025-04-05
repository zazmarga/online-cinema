from datetime import timedelta
from io import BytesIO

import pytest
from PIL import Image

from src.database.models import UserModel, UserProfileModel
from src.tests.conftest import test_settings


@pytest.mark.unit
def test_create_user_profile_with_avatar(
    client, db_session, seed_user_groups, jwt_manager, minio_client
):
    """
    Positive test for creating a user profile.

    Steps:
    1. Create a test user and activate them.
    2. Generate an access token using `jwt_manager`.
    3. Send a profile creation request with an avatar.
    4. Verify that the avatar was uploaded to s3 storage.
    5. Verify that the profile was created in the database.
    6. Clean s3 storage after test.
    """

    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    access_token = jwt_manager.create_access_token({"user_id": user.id})

    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    avatar_key = f"avatars/{user.id}_avatar.jpg"

    profile_url = f"/api/v1/profiles/{user.id}/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    profile_data = response.json()

    assert profile_data["first_name"] == "john"
    assert profile_data["last_name"] == "doe"
    assert profile_data["gender"] == "man"
    assert profile_data["date_of_birth"] == "1990-01-01"
    assert "avatar" in profile_data, "Avatar URL is missing!"

    avatar_url = profile_data["avatar"]

    bucket_name = test_settings.S3_BUCKET_NAME
    file_name = avatar_key

    minio_response = minio_client.stat_object(bucket_name, file_name)
    objects = minio_client.list_objects(bucket_name, prefix="avatars/", recursive=True)
    print(f"\nStorage contains: {[(obj.object_name, obj.size) for obj in objects]}")
    assert (
        minio_response is not None
    ), f"Minio object '{file_name}' does not exist in bucket '{bucket_name}'"

    expected_url = minio_client.get_presigned_url(
        method="get", bucket_name=bucket_name, object_name=file_name
    )
    assert expected_url.startswith(
        avatar_url
    ), f"Avatar URL is missing! Expected: {expected_url}, but got: {avatar_url}"

    profile_in_db = (
        db_session.query(UserProfileModel).filter_by(user_id=user.id).first()
    )
    assert profile_in_db, f"Profile for user {user.id} should exist!"

    assert profile_in_db.first_name == "john", "First name is incorrect!"
    assert profile_in_db.last_name == "doe", "Last name is incorrect!"
    assert profile_in_db.gender.name == "man", "Gender is incorrect!"
    assert (
        str(profile_in_db.date_of_birth) == "1990-01-01"
    ), "Date of birth is incorrect!"
    assert profile_in_db.info == "This is a test profile.", "Profile info is incorrect!"
    assert profile_in_db.avatar == avatar_key, "Avatar key in database does not match!"


@pytest.mark.unit
@pytest.mark.parametrize(
    "headers, expected_status, expected_detail",
    [
        (None, 401, "Authorization header is missing"),
        (
            {"Authorization": "Token invalid_token"},
            401,
            "Invalid Authorization header format. Expected 'Bearer <token>'",
        ),
    ],
)
def test_create_user_profile_invalid_auth(
    client, headers, expected_status, expected_detail
):
    """
    Test profile creation with missing or incorrectly formatted Authorization header.

    Expected result:
    - The request should fail with 401 Unauthorized.
    - The appropriate error message should be returned.

    This test runs twice with:
    1. No Authorization header at all.
    2. Incorrect Authorization format (e.g., "Token invalid_token").
    """

    profile_url = "/api/v1/profiles/1/profile/"

    response = client.post(profile_url, headers=headers)

    assert (
        response.status_code == expected_status
    ), f"Expected {expected_status}, got {response.status_code}"
    assert (
        response.json()["detail"] == expected_detail
    ), f"Unexpected error message: {response.json()['detail']}"


@pytest.mark.unit
def test_create_user_profile_expired_token(client, jwt_manager):
    """
    Test profile creation with an expired access token.

    Expected result:
    - The request should fail with 401 Unauthorized.
    - The error message should be: "Token has expired."
    """

    expired_token = jwt_manager.create_access_token(
        {"user_id": 1}, expires_delta=timedelta(days=-5)
    )

    profile_url = "/api/v1/profiles/1/profile/"
    headers = {"Authorization": f"Bearer {expired_token}"}

    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "Test profile."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    assert (
        response.json()["detail"] == "Token has expired."
    ), f"Unexpected error message: {response.json()['detail']}"


@pytest.mark.unit
def test_admin_creates_user_profile(
    db_session, seed_user_groups, jwt_manager, client, minio_client
):
    """
    Test that an admin can create a profile for another user.

    Steps:
    1. Create an admin user and a regular user.
    2. Generate an access token for the admin.
    3. Send a request to create a profile for the regular user.
    4. Verify that the profile was created successfully.
    """

    admin_user = UserModel.create(
        email="admin@example.com", raw_password="AdminPass123!", group_id=3
    )
    admin_user.is_active = True
    db_session.add(admin_user)

    regular_user = UserModel.create(
        email="user@example.com", raw_password="UserPass123!", group_id=1
    )
    regular_user.is_active = True
    db_session.add(regular_user)

    db_session.commit()

    admin_token = jwt_manager.create_access_token({"user_id": admin_user.id})

    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    avatar_key = f"avatars/{regular_user.id}_avatar.jpg"

    profile_url = f"/api/v1/profiles/{regular_user.id}/profile/"
    headers = {"Authorization": f"Bearer {admin_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "Test profile."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    profile_data = response.json()

    assert profile_data["first_name"] == "john"
    assert profile_data["last_name"] == "doe"
    assert profile_data["gender"] == "man"
    assert profile_data["date_of_birth"] == "1990-01-01"
    assert "avatar" in profile_data, "Avatar URL is missing!"

    avatar_url = profile_data["avatar"]
    bucket_name = test_settings.S3_BUCKET_NAME
    file_name = avatar_key

    minio_response = minio_client.stat_object(bucket_name, file_name)
    objects = minio_client.list_objects(bucket_name, prefix="avatars/", recursive=True)
    print(f"\nStorage contains: {[(obj.object_name, obj.size) for obj in objects]}")
    assert (
        minio_response is not None
    ), f"Minio object '{file_name}' does not exist in bucket '{bucket_name}'"

    expected_url = minio_client.get_presigned_url(
        method="get", bucket_name=bucket_name, object_name=file_name
    )
    assert expected_url.startswith(
        avatar_url
    ), f"Avatar URL is missing! Expected: {expected_url}, but got: {avatar_url}"

    profile_in_db = (
        db_session.query(UserProfileModel).filter_by(user_id=regular_user.id).first()
    )
    assert profile_in_db, f"Profile for user {regular_user.id} should exist!"

    assert profile_in_db.first_name == "john", "First name is incorrect!"
    assert profile_in_db.last_name == "doe", "Last name is incorrect!"
    assert profile_in_db.gender.name == "man", "Gender is incorrect!"
    assert (
        str(profile_in_db.date_of_birth) == "1990-01-01"
    ), "Date of birth is incorrect!"
    assert profile_in_db.info == "Test profile.", "Profile info is incorrect!"
    assert profile_in_db.avatar == avatar_key, "Avatar key in database does not match!"


@pytest.mark.unit
def test_user_cannot_create_another_user_profile(
    db_session, seed_user_groups, jwt_manager, client, minio_client
):
    """
    Test that a regular user cannot create a profile for another user.

    Steps:
    1. Create two regular users.
    2. Generate an access token for the first user.
    3. Attempt to create a profile for the second user.
    4. Verify that the request fails with 403 Forbidden.
    """

    user_1 = UserModel.create(
        email="user1@example.com", raw_password="User1Pass123!", group_id=1
    )  # 1 = User
    user_1.is_active = True
    db_session.add(user_1)

    user_2 = UserModel.create(
        email="user2@example.com", raw_password="User2Pass123!", group_id=1
    )  # 1 = User
    user_2.is_active = True
    db_session.add(user_2)

    db_session.commit()

    user_1_token = jwt_manager.create_access_token({"user_id": user_1.id})

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    profile_url = f"/api/v1/profiles/{user_2.id}/profile/"
    headers = {"Authorization": f"Bearer {user_1_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "Attempting unauthorized profile creation."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    assert (
        response.json()["detail"] == "You don't have permission to edit this profile."
    ), f"Unexpected error message: {response.json()['detail']}"

    profile_in_db = (
        db_session.query(UserProfileModel).filter_by(user_id=user_2.id).first()
    )
    assert profile_in_db is None, "Profile should not have been created!"


@pytest.mark.unit
def test_inactive_user_cannot_create_profile(
    db_session, seed_user_groups, jwt_manager, client, minio_client
):
    """
    Test that an inactive user cannot create a profile.

    Steps:
    1. Create a user but do not activate them.
    2. Generate an access token for the user.
    3. Attempt to create a profile.
    4. Verify that the request fails with 401 Unauthorized.
    """

    user = UserModel.create(
        email="inactive@example.com", raw_password="TestPassword123!", group_id=1
    )  # 1 = User
    user.is_active = False
    db_session.add(user)
    db_session.commit()

    access_token = jwt_manager.create_access_token({"user_id": user.id})

    img = Image.new("RGB", (100, 100), color="gray")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    profile_url = f"/api/v1/profiles/{user.id}/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "Attempting to create a profile while inactive."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    assert (
        response.json()["detail"] == "User not found or not active."
    ), f"Unexpected error message: {response.json()['detail']}"

    profile_in_db = (
        db_session.query(UserProfileModel).filter_by(user_id=user.id).first()
    )
    assert profile_in_db is None, "Profile should not have been created!"


@pytest.mark.unit
def test_cannot_create_profile_twice(
    db_session, seed_user_groups, jwt_manager, client, minio_client
):
    """
    Test that a user cannot create a profile twice.

    Steps:
    1. Create and activate a user.
    2. Create a profile for the user.
    3. Attempt to create another profile.
    4. Verify that the request fails with 400 Bad Request.
    """

    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()

    access_token = jwt_manager.create_access_token({"user_id": user.id})

    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    profile_url = f"/api/v1/profiles/{user.id}/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response1 = client.post(profile_url, headers=headers, files=files)
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}"

    response2 = client.post(profile_url, headers=headers, files=files)

    assert response2.status_code == 400, f"Expected 400, got {response2.status_code}"
    assert (
        response2.json()["detail"] == "User already has a profile."
    ), f"Unexpected error message: {response2.json()['detail']}"

    profiles_count = (
        db_session.query(UserProfileModel).filter_by(user_id=user.id).count()
    )
    assert profiles_count == 1, f"Expected only one profile, but found {profiles_count}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "first_name, last_name, expected_error",
    [
        ("John1", "Doe", "John1 contains non-english letters"),
        ("John", "Doe1", "Doe1 contains non-english letters"),
    ],
)
def test_profile_creation_invalid_name(
    client, jwt_manager, first_name, last_name, expected_error, minio_client
):
    """
    Test that profile creation fails if the first_name or last_name contains non-English letters.
    """

    access_token = jwt_manager.create_access_token({"user_id": 1})

    profile_url = "/api/v1/profiles/1/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, first_name),
        "last_name": (None, last_name),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.jpg", BytesIO(b"fake_image"), "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    assert expected_error in str(
        response.json()
    ), f"Unexpected error message: {response.json()}"


@pytest.mark.unit
def test_profile_creation_invalid_avatar_format(client, jwt_manager, minio_client):
    """
    Test that profile creation fails if the avatar has an unsupported format.
    """

    access_token = jwt_manager.create_access_token({"user_id": 1})

    profile_url = "/api/v1/profiles/1/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.gif", BytesIO(b"fake_image"), "image/gif"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    assert "Invalid image format" in str(
        response.json()
    ), f"Unexpected error message: {response.json()}"


@pytest.mark.unit
def test_profile_creation_avatar_too_large(
    db_session, client, jwt_manager, minio_client
):
    """
    Test that profile creation fails if the avatar exceeds 1MB.
    """

    access_token = jwt_manager.create_access_token({"user_id": 1})

    img = Image.new("RGB", (10000, 10000), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    profile_url = "/api/v1/profiles/1/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    assert "Image size exceeds 1 MB" in str(
        response.json()
    ), f"Unexpected error message: {response.json()}"


@pytest.mark.unit
def test_profile_creation_invalid_gender(client, jwt_manager, minio_client):
    """
    Test that profile creation fails if gender is invalid.
    """

    access_token = jwt_manager.create_access_token({"user_id": 1})

    profile_url = "/api/v1/profiles/1/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "other"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.jpg", BytesIO(b"fake_image"), "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    assert "Gender must be one of" in str(
        response.json()
    ), f"Unexpected error message: {response.json()}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "birth_date, expected_error",
    [
        ("1800-01-01", "Invalid birth date - year must be greater than 1900."),
        ("2010-01-01", "You must be at least 18 years old to register."),
    ],
)
def test_profile_creation_invalid_birth_date(
    client, jwt_manager, birth_date, expected_error, minio_client
):
    """
    Test that profile creation fails if birth_date is invalid.
    """

    access_token = jwt_manager.create_access_token({"user_id": 1})

    profile_url = "/api/v1/profiles/1/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, birth_date),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.jpg", BytesIO(b"fake_image"), "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    assert expected_error in str(
        response.json()
    ), f"Unexpected error message: {response.json()}"


@pytest.mark.unit
@pytest.mark.parametrize("info_value", ["", "   "])
def test_profile_creation_empty_info(client, jwt_manager, info_value, minio_client):
    """
    Test that profile creation fails if info field is empty or contains only spaces.
    """

    access_token = jwt_manager.create_access_token({"user_id": 1})

    profile_url = "/api/v1/profiles/1/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, info_value),
        "avatar": ("avatar.jpg", BytesIO(b"fake_image"), "image/jpeg"),
    }

    response = client.post(profile_url, headers=headers, files=files)

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    assert "Info field cannot be empty or contain only spaces." in str(
        response.json()
    ), f"Unexpected error message: {response.json()}"
