from typing import List, Any

from sqlalchemy import update, func
from sqlalchemy.orm import Session

from src.database.models.movies import MovieModel, FavoriteMovieModel
from src.schemas.movies import MovieListItemSchema


def fetch_list_favorite_movies(
    session: Session, user_id: int
) -> List[MovieListItemSchema]:
    movies = (
        session.query(MovieModel)
        .join(FavoriteMovieModel, FavoriteMovieModel.c.movie_id == MovieModel.id)
        .filter(FavoriteMovieModel.c.user_id == user_id)
        .all()
    )

    return movies


def add_movie_to_table(session, user_id, movie_id, table_name):
    insert = table_name.insert().values(user_id=user_id, movie_id=movie_id)
    session.execute(insert)
    session.commit()


def remove_movie_from_table(session, user_id, movie_id, table_name):
    delete = table_name.delete().where(
        (table_name.c.user_id == user_id) & (table_name.c.movie_id == movie_id)
    )
    session.execute(delete)
    session.commit()


def check_record_exists(session: Session, user_id: int, movie_id: int, table_name):
    like_exists = (
        session.query(table_name)
        .filter(table_name.c.user_id == user_id, table_name.c.movie_id == movie_id)
        .first()
    )
    return like_exists is not None


def update_table_field(
    session: Session, user_id: int, movie_id: int, table_name, table_field, value: Any
):
    stmt = (
        update(table_name)
        .where(table_name.c.user_id == user_id, table_name.c.movie_id == movie_id)
        .values({table_field: value})
    )
    session.execute(stmt)
    session.commit()


def get_random_movie(db_session: Session):
    random_movie = db_session.query(MovieModel).order_by(func.random()).first()
    return random_movie
