from sqlalchemy.orm import Session

from src.database.models.carts import PurchasedMovieModel
from src.database.models.orders import OrderItemModel, OrderModel, OrderStatusEnum


def movie_is_purchased(session: Session, user_id: int, movie_id: int) -> bool:
    purchased = (
        session.query(PurchasedMovieModel)
        .filter(
            PurchasedMovieModel.c.user_id == user_id,
            PurchasedMovieModel.c.movie_id == movie_id,
        )
        .first()
    )
    return purchased is not None


def movie_in_other_orders(session: Session, user_id: int, movie_id: int) -> bool:
    user_orders_ids = (
        session.query(OrderModel)
        .filter(
            OrderModel.user_id == user_id, OrderModel.status != OrderStatusEnum.CANCELED
        )
        .all()
    )
    user_orders_ids = [order.id for order in user_orders_ids]

    orders_with_movie = (
        session.query(OrderItemModel.order_id)
        .filter(
            OrderItemModel.movie_id == movie_id,
            OrderItemModel.order_id.in_(user_orders_ids),
        )
        .distinct()
        .all()
    )

    return len(orders_with_movie) >= 1
