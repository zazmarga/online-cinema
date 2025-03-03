from typing import List

from pydantic import BaseModel

from src.schemas.examples.orders import (
    order_list_schema_example,
    order_list_full_schema_example,
)


class OrderItemListSchema(BaseModel):
    id: int
    date: str
    movies: List[str]
    total_amount: float
    status: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [order_list_schema_example]},
    }


class OrderListSchema(BaseModel):
    orders: List[OrderItemListSchema]


class OrderListFullSchema(OrderItemListSchema):
    user_id: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [order_list_full_schema_example]},
    }
