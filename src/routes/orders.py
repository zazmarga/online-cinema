from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_filter import FilterDepends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette import status

from src.config.dependencies import get_jwt_auth_manager
from src.database.filters.orders import OrderFilter
from src.database.models.accounts import UserGroupModel, UserModel, UserGroupEnum
from src.database.models.carts import CartModel, CartItemModel
from src.database.models.movies import MovieModel, ConfirmationEnum
from src.database.models.orders import OrderModel, OrderItemModel, OrderStatusEnum
from src.database.services.orders import movie_is_purchased, movie_in_other_orders
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.schemas.accounts import MessageResponseSchema
from src.schemas.orders import OrderListSchema, OrderItemListSchema, OrderListFullSchema
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
                    "example": {"detail": "An error occurred while creating the order."}
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


@router.get(
    "/user/all/",
    response_model=OrderListSchema,
    summary="Get list of all user's orders.",
    description="This endpoint shows list of all user's orders.",
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
            "description": "Not found.",
            "content": {
                "application/json": {"example": {"detail": "User's order not found."}}
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while getting users orders."
                    }
                }
            },
        },
    },
)
def get_list_user_orders(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> OrderListSchema:
    """
    Get list of orders.
    This endpoint shows list of all user's orders.

    :return: OrderListSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    orders = db.query(OrderModel).filter(OrderModel.user_id == user_id).all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User's order not found."
        )

    response_orders = []
    for order in orders:
        order_items = (
            db.query(OrderItemModel, MovieModel.name)
            .join(MovieModel, OrderItemModel.movie_id == MovieModel.id)
            .filter(OrderItemModel.order_id == order.id)
        )
        movies = [item.name for item in order_items]
        response_orders.append(
            OrderItemListSchema(
                id=order.id,
                date=order.created_at.strftime("%Y-%m-%d %H:%M"),
                movies=movies,
                total_amount=order.total_amount,
                status=order.status,
            )
        )

    return OrderListSchema(orders=response_orders)


@router.post(
    "/user/{order_id}/cancel/",
    response_model=MessageResponseSchema,
    summary="Canceling user orders.",
    description="This endpoint allows to cancel user order by order ID.",
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
            "description": "Not found.",
            "content": {
                "application/json": {"example": {"detail": "User's order not found."}}
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while actions with users orders."
                    }
                }
            },
        },
    },
)
def cancel_order(
    order_id: int,
    to_cancel: Optional[ConfirmationEnum] = Query(
        None, description="Cancel the order? (ex.: to_cancel:: yes)"
    ),
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema | None:
    """
    Canceling user orders.
    This endpoint allows to cancel user order by order ID.

    :return: OrderListSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    order = (
        db.query(OrderModel)
        .filter(OrderModel.user_id == user_id, OrderModel.id == order_id)
        .first()
    )

    if (
        not order
        or order.status == OrderStatusEnum.CANCELED
        or order.status == OrderStatusEnum.PAID
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User's order with this ID not found or is already paid, or canceled.",
        )

    if to_cancel:
        try:
            if order.status == OrderStatusEnum.PENDING:
                order.status = OrderStatusEnum.CANCELED
                db.commit()
            elif order.status == OrderStatusEnum.PAID:
                return MessageResponseSchema(
                    message="This order has already been paid for, you can cancel it through the return procedure."
                )
            return MessageResponseSchema(
                message="Order has been cancelled successfully."
            )

        except SQLAlchemyError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )


@router.get(
    "/",
    response_model=List[OrderListFullSchema],
    summary="Get list of all orders.",
    description="<h3>This endpoint shows list of all orders for all users. Allowed only for ADMIN users. </h3>"
    "<p>Optional:  Filtering orders by user_id/list(user_id), ex.: 2,3; <br>"
    "by start date (inclusive), ex.: YYYY-MM-DD; <br>"
    "by end date (inclusive), ex.: YYYY-MM-DD; <br>"
    "by status, ex.: paid  (should be one of: 'pending', 'paid' or 'canceled').</p>",
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
            "description": "Not found.",
            "content": {
                "application/json": {"example": {"detail": "User's order not found."}}
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {"detail": "An error occurred while getting orders."}
                }
            },
        },
    },
)
def get_list_orders(
    order_filter: Optional[OrderFilter] = FilterDepends(OrderFilter),
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> List[OrderListFullSchema]:
    """
    Get list of all orders.
    This endpoint shows list of all orders for all users. Allowed only for ADMIN users.
    Optional:  Filtering orders
    by user_id/list(user_id), ex.: 2,3;
    by start date (inclusive), ex.: YYYY-MM-DD;
    by end date (inclusive), ex.: YYYY-MM-DD;
    by status, ex.: paid  (should be one of: 'pending', 'paid' or 'canceled').

    :param order_filter: OrderFilter - filtering orders
    :return: List[OrderListFullSchema]
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_group = (
        db.query(UserGroupModel).join(UserModel).filter(UserModel.id == user_id).first()
    )

    if user_group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do this operation.",
        )

    query = db.query(OrderModel)

    if order_filter:
        query = order_filter.filter(query)

    orders = query.all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Orders not found."
        )

    response_orders = []
    for order in orders:
        order_items = (
            db.query(OrderItemModel, MovieModel.name)
            .join(MovieModel, OrderItemModel.movie_id == MovieModel.id)
            .filter(OrderItemModel.order_id == order.id)
        )
        movies = [item.name for item in order_items]
        response_orders.append(
            OrderListFullSchema(
                id=order.id,
                user_id=order.user_id,
                date=order.created_at.strftime("%Y-%m-%d %H:%M"),
                movies=movies,
                total_amount=order.total_amount,
                status=order.status,
            )
        )

    return response_orders
