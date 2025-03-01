from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.testing.pickleable import User

from src.config.dependencies import get_jwt_auth_manager
from src.database.models.carts import CartModel, CartItemModel, PurchasedMovieModel
from src.database.models.movies import MovieModel
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.schemas.accounts import MessageResponseSchema
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.post(
    "/user-cart/add-movie/",
    response_model=MessageResponseSchema,
    summary="Add movie to cart",
    description="This endpoint adds movie to current user cart by movie ID.",
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
        404: {
            "description": "Not found",
            "content": {
                "application/json": {
                    "examples": {
                        "user_not_found": {
                            "summary": "User not found",
                            "value": {"detail": "User not found."},
                        },
                        "movie_not_found": {
                            "summary": "Movie not found",
                            "value": {"detail": "Movie not found."},
                        },
                    }
                }
            },
        },
        409: {
            "description": "Conflict.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with this ID already is purchased by user."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while updating the user cart."
                    }
                }
            },
        },
    },
)
def add_movie_to_user_cart(
    movie_id: int,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema:
    """
    Add movie to current user cart by movie ID.

    :param movie_id:
    :param token:
    :param db:
    :param jwt_manager:

    :return: MessageResponseSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    movie = db.query(MovieModel).filter(MovieModel.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found."
        )
    existing_purchased_movie = (
        db.query(PurchasedMovieModel)
        .filter(
            PurchasedMovieModel.c.movie_id == movie_id,
            PurchasedMovieModel.c.user_id == current_user_id,
        )
        .one_or_none()
    )
    if existing_purchased_movie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie with this ID already is purchased by user.",
        )

    user_cart = db.get(CartModel, current_user_id)
    if not user_cart:
        user_cart = CartModel(user_id=current_user_id)
        db.add(user_cart)
        db.flush()

    item_to_cart = CartItemModel(cart_id=user_cart.id, movie_id=movie.id)
    db.add(item_to_cart)
    db.commit()
    db.refresh(item_to_cart)

    return MessageResponseSchema(
        message="The movie has been added to user cart successfully."
    )
