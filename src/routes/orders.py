from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette import status

from src.config.dependencies import get_jwt_auth_manager
from src.database.models.carts import CartModel, CartItemModel
from src.database.models.movies import MovieModel
from src.database.models.orders import OrderModel, OrderItemModel
from src.database.services.orders import movie_is_purchased, movie_in_other_orders
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.schemas.accounts import MessageResponseSchema
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.post(
    "/user/add-order/",
    response_model=MessageResponseSchema,
    summary="Add new order",
    description="This endpoint adds new order using list movies from  user's cart."
    "If any movie has already been purchased by the user or is in another order, "
    "it will be removed from the order and the user will be notified. "
    "If the price of any  movie has changed since it was added to the cart, "
    "it will be updated to the current price.",
    status_code=status.HTTP_201_CREATED,
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
            "description": "Not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "User's cart not found or empty."}
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
def add_new_order(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema:
    """
    Add a new order.
    This endpoint adds new order using list movies from  user's cart.
    If any movie has already been purchased by the user or is in another order,
    it will be removed from the order and the user will be notified.
    If the price of any  movie has changed since it was added to the cart,
    it will be updated to the current price.

    :return:
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
            detail="User's cart not found or empty.",
        )

    cart_items = (
        db.query(CartItemModel).filter(CartItemModel.cart_id == user_cart.id).all()
    )

    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User's cart not found or empty.",
        )

    message = ""
    new_order = OrderModel(
        user_id=current_user_id,
    )
    db.add(new_order)
    db.flush()

    for item in cart_items:
        movie = db.get(MovieModel, item.movie_id)

        if (
            not movie
            or movie_is_purchased(db, current_user_id, movie.id)
            or movie_in_other_orders(db, current_user_id, movie.id)
        ):
            message = message + f"Movie with id={movie.id} deleted from cart. "
        else:
            new_order_item = OrderItemModel(
                order_id=new_order.id, movie_id=movie.id, price_at_order=movie.price
            )
            db.add(new_order_item)
            new_order.total_amount += movie.price
            db.flush()

        db.delete(item)
        db.flush()

    order_items = (
        db.query(OrderItemModel).filter(OrderItemModel.order_id == new_order.id).all()
    )

    if not order_items:
        message = message + f"Order has not been created."
        db.delete(new_order)
    else:
        message = message + f"Order has been created successfully."

    try:
        db.commit()
        return MessageResponseSchema(message=message)

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
