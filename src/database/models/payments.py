from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, DateTime, DECIMAL, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class PaymentStatusEnum(str, Enum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentItemModel(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    price_at_payment: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)

    payment = relationship("PaymentModel", back_populates="payment_items")

    order_item = relationship("OrderItemModel", back_populates="payment_item")

    def __repr__(self) -> str:
        return f"PaymentItem(id={self.id}, payment_id={self.payment_id})"


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    status: Mapped[PaymentStatusEnum] = mapped_column(
        nullable=False, default=PaymentStatusEnum.SUCCESSFUL
    )
    amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    external_payment_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    user = relationship("UserModel", back_populates="payments")

    order = relationship("OrderModel", back_populates="payment")

    payment_items = relationship("PaymentItemModel", back_populates="payment")

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, order_id={self.order_id}, status={self.status})>"
