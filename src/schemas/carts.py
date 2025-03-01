from typing import List

from pydantic import BaseModel


class CartItemSchema(BaseModel):
    movie_id: int
    name: str
    price: float
    genres: str
    year: int

    model_config = {
        "from_attributes": True,
    }


class UserCartSchema(BaseModel):
    cart_items: List[CartItemSchema]


class CartListSchema(UserCartSchema):
    user_id: int

    model_config = {
        "from_attributes": True,
    }
