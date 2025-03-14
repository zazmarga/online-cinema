from typing import cast

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import HttpUrl
from sqlalchemy.orm import Session

from src.config.dependencies import get_jwt_auth_manager, get_s3_storage_client
from src.database.models.accounts import UserGroupModel, UserModel, UserGroupEnum
from src.database.models.profiles import UserProfileModel, GenderEnum
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.exceptions.storages import S3FileUploadError
from src.schemas.profiles import ProfileResponseSchema, ProfileCreateSchema
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface
from src.storages import S3StorageInterface

router = APIRouter()


@router.post(
    "/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="Create user profile",
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    user_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: Session = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    profile_data: ProfileCreateSchema = Depends(ProfileCreateSchema.from_form),
) -> ProfileResponseSchema:
    """
    Creates a user profile.

    Steps:
    - Validate user authentication token.
    - Check if the user already has a profile.
    - Upload avatar to S3 storage.
    - Store profile details in the database.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if user_id != token_user_id:
        user_group = (
            db.query(UserGroupModel)
            .join(UserModel)
            .filter(UserModel.id == token_user_id)
            .first()
        )

        if not user_group or user_group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile.",
            )

    user = db.query(UserModel).filter_by(id=user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    existing_profile = db.query(UserProfileModel).filter_by(user_id=user_id).first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    avatar_bytes = profile_data.avatar.file.read()
    avatar_key = f"avatars/{user_id}_{profile_data.avatar.filename}"

    try:
        s3_client.upload_file(file_name=avatar_key, file_data=avatar_bytes)
    except S3FileUploadError as e:
        print(f"Error uploading avatar to S3: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later.",
        )

    new_profile = UserProfileModel(
        user_id=cast(int, user_id),
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=cast(GenderEnum, profile_data.gender),
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_key,
    )

    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    avatar_url = s3_client.get_file_url(new_profile.avatar)

    return ProfileResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=cast(HttpUrl, avatar_url),
    )


# @router.delete(
#     "/{user_id}/")
# def delete_profile(
#     user_id: int,
#     db: Session = Depends(get_db)
# ):
#     profile = db.query(UserProfileModel).filter_by(user_id=user_id).first()
#
#     db.delete(profile)
#     db.commit()
#
#     return HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail="User's profile deleted.")
