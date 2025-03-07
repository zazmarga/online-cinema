from sqlalchemy.orm import Session

from src.database.models.orders import OrderModel


def check_prices_of_order_items(session: Session, order_id: int) -> float:
    order = session.query(OrderModel).filter(OrderModel.id == order_id).first()

    total_price = 0
    for order_item in order.order_items:
        total_price += order_item.movie.price

    return total_price
