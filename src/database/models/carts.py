from datetime import datetime, timezone
from enum import unique

from sqlalchemy import ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column

from src.database.models.accounts import UserModel
from src.database.models.base import Base
from src.database.models.movies import MovieModel


class CartModel(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    user: Mapped[UserModel] = relationship("UserModel", back_populates="cart")

    __table_args__ = (UniqueConstraint("user_id"),)

    def __repr__(self):
        return f"<Cart(user_id='{self.user_id}')>"


class CartItemModel(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = relationship(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = relationship(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )

    carts = relationship(CartModel, back_populates="cart_items")
    movies = relationship(MovieModel, back_populates="cart_items")

    __table_args__ = (
        UniqueConstraint("cart_id", "movie_id", name="unique_movie_constraint"),
    )

    def __repr__(self):
        return f"<CartItem(cart_id='{self.cart_id}', movie_id='{self.movie_id}')>"
