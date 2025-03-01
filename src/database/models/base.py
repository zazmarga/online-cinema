from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    @classmethod
    def default_order_by(cls):
        return None


import src.database.models.accounts
import src.database.models.movies
import src.database.models.carts
