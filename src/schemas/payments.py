from typing import List

from pydantic import BaseModel


class PaymentItemListSchema(BaseModel):
    id: int
    date: str
    amount: float
    status: str

    model_config = {
        "from_attributes": True,
   }


class PaymentListSchema(BaseModel):
    payments: List[PaymentItemListSchema]


class PaymentListFullSchema(PaymentItemListSchema):
    user_id: int

    model_config = {
        "from_attributes": True,
    }
