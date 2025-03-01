from sqlite3 import IntegrityError
from typing import List, Optional

from fastapi import APIRouter, status, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config.dependencies import get_jwt_auth_manager
from src.database.models.accounts import UserGroupModel, UserModel, UserGroupEnum
from src.database.models.carts import CartModel, CartItemModel, PurchasedMovieModel
from src.database.models.movies import MovieModel, ConfirmationEnum
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.schemas.accounts import MessageResponseSchema
from src.schemas.carts import UserCartSchema, CartItemSchema, CartListSchema
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
            detail="Movie with this ID already is purchased by user. Repeat purchases are not allowed.",
        )
    try:
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

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/user-cart/",
    response_model=UserCartSchema,
    summary="Get list movies in user's cart",
    description="This endpoint shows list movies in a cart of current user.",
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
            "description": "Not found cart.",
            "content": {
                "application/json": {"example": {"detail": "User cart is empty."}}
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {"detail": "An error occurred while get the user cart."}
                }
            },
        },
    },
)
def get_user_cart(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserCartSchema:
    """
    Get list movies in user's cart.

    :param token:
    :param db:
    :param jwt_manager:

    :return: UserCartSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_cart = db.get(CartModel, current_user_id)
    if not user_cart:
        user_cart = CartModel(user_id=current_user_id)
        db.add(user_cart)
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User cart is empty."
        )

    movies_in_cart = [item.movies for item in user_cart.cart_items]
    if not movies_in_cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User cart is empty."
        )

    cart_items = []
    for movie in movies_in_cart:
        genres = ", ".join([genre.name for genre in movie.genres])
        cart_items.append(
            CartItemSchema(
                movie_id=movie.id,
                name=movie.name,
                price=movie.price,
                genres=genres,
                year=movie.year,
            )
        )

    return UserCartSchema(cart_items=cart_items)


@router.post(
    "/user-cart/update/",
    response_model=MessageResponseSchema,
    summary="Update user's cart",
    description="This endpoint update current users cart: "
    "remove movie by movie ID "
    "or clear cart.",
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {"detail": "Authorization header is missing."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with the given ID was not found in user's cart."
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
def update_user_cart(
    movie_id: Optional[int] = Query(
        None, description="Remove the movie from cart by movie ID. (ex.: movie_id: 3)"
    ),
    clear_cart: Optional[ConfirmationEnum] = Query(
        None, description="Clear the cart? (ex.: clear_cart: yes)"
    ),
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema:
    """
    This endpoint update current users cart:
    remove a movie by movie ID or clear cart.

    :param movie_id:
    :param clear_cart: ConfirmationEnum or None, confirmation to clear cart (remove all movies).
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

    user_cart = db.get(CartModel, current_user_id)
    if not user_cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found in user's cart.",
        )
    try:
        if clear_cart:
            db.query(CartItemModel).filter(
                CartItemModel.cart_id == user_cart.id
            ).delete()
            db.commit()

            return MessageResponseSchema(
                message="User's cart has been cleared successfully."
            )

        if movie_id:
            cart_item = (
                db.query(CartItemModel)
                .filter(
                    CartItemModel.movie_id == movie_id,
                    CartItemModel.cart_id == user_cart.id,
                )
                .first()
            )

            if not cart_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Movie with the given ID was not found in user's cart.",
                )

            db.delete(cart_item)
            db.commit()
            db.refresh(user_cart)

            return MessageResponseSchema(
                message="User's cart has been updated successfully."
            )

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/all/",
    response_model=List[CartListSchema],
    summary="Get all users carts",
    description="This endpoint shows all users cart with list movies in each cart. "
    "Allowed only for ADMIN users.",
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
                    "example": {
                        "detail": "You don't have permission to do this operation."
                    }
                }
            },
        },
        404: {
            "description": "Not found any carts.",
            "content": {
                "application/json": {"example": {"detail": "Users carts not found."}}
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while get list of users carts."
                    }
                }
            },
        },
    },
)
def get_list_carts(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> List[CartListSchema]:
    """
    Get list of users carts with list of movies in each user's cart.
    Allowed only for ADMIN users.

    :param token:
    :param db:
    :param jwt_manager:

    :return: List[UserCartSchema]
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        current_user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_group = (
        db.query(UserGroupModel)
        .join(UserModel)
        .filter(UserModel.id == current_user_id)
        .first()
    )

    if user_group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do this operation.",
        )

    user_carts = db.query(CartModel).all()

    if not user_carts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Users carts not found."
        )

    list_carts = []

    for user_cart in user_carts:

        movies_in_cart = [item.movies for item in user_cart.cart_items]

        cart_items = []
        for movie in movies_in_cart:
            genres = ", ".join([genre.name for genre in movie.genres])
            cart_items.append(
                CartItemSchema(
                    movie_id=movie.id,
                    name=movie.name,
                    price=movie.price,
                    genres=genres,
                    year=movie.year,
                )
            )
        list_carts.append(
            CartListSchema(user_id=user_cart.user_id, cart_items=cart_items)
        )

    return list_carts
