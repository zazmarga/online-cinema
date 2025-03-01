from pydantic import BaseModel


class CartItemSchema(BaseModel):
    name: str
    price: float
    genres: str
    year: int

    model_config = {
        "from_attributes": True,
    }


class UserCartSchema(BaseModel):
    cart_items: list[CartItemSchema]
