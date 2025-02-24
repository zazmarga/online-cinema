from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.database.models.movies import MovieModel
from src.database.session import get_db
from src.schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
)
from src.security.http import get_token


router = APIRouter()


@router.get(
    "/movies-list/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    description=(
        "<h3>This endpoint retrieves a paginated list of movies from the database. "
        "Clients can specify the `page` number and the number of items per page using `per_page`. "
        "The response includes details about the movies, total pages, and total items, "
        "along with links to the previous and next pages if applicable.</h3>"
    ),
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {"detail": "Authorization header is missing."}
                }
            },
        },
        404: {
            "description": "No movies found.",
            "content": {
                "application/json": {"example": {"detail": "No movies found."}}
            },
        },
    },
)
def get_movie_list(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Fetch a paginated list of movies from the database.

    This function retrieves a paginated list of movies, allowing the client to specify
    the page number and the number of items per page. It calculates the total pages
    and provides links to the previous and next pages when applicable.

    :param page: The page number to retrieve (1-based index, must be >= 1).
    :type page: int
    :param per_page: The number of items to display per page (must be between 1 and 20).
    :type per_page: int
    :param token: Token used to authenticate.
    :type token: str
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session

    :return: A response containing the paginated list of movies and metadata.
    :rtype: MovieListResponseSchema

    :raises HTTPException: Raises a 401 if user unauthorized. Raises a 404 error if no movies are found for the requested page.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing.",
        )

    offset = (page - 1) * per_page

    query = db.query(MovieModel).order_by()

    order_by = MovieModel.default_order_by()
    if order_by:
        query = query.order_by(*order_by)

    total_items = query.count()
    movies = query.offset(offset).limit(per_page).all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]

    total_pages = (total_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=(
            f"/movies/movies-list?page={page - 1}&per_page={per_page}"
            if page > 1
            else None
        ),
        next_page=(
            f"/movies/movies-list?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.get(
    "/movie-detail/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    description=(
        "<h3>Fetch detailed information about a specific movie by its unique ID. "
        "This endpoint retrieves all available details for the movie, such as "
        "its name, genre, crew, uuid, votes and others. If the movie with the given "
        "ID is not found, a 404 error will be returned."
        "Only for register users. If not token, a 401 error will be returned.</h3>"
    ),
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {"detail": "Authorization header is missing."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
)
def get_movie_by_id(
    movie_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
) -> MovieDetailSchema:
    """
    Retrieve detailed information about a specific movie by its ID.

    This function fetches detailed information about a movie identified by its unique ID.
    If the movie does not exist, a 404 error is returned.

    :param movie_id: The unique identifier of the movie to retrieve.
    :type movie_id: int
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: Token used to authenticate.
    :type token: str

    :return: The details of the requested movie.
    :rtype: MovieDetailResponseSchema

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing.",
        )

    movie = (
        db.query(MovieModel)
        .options(
            joinedload(MovieModel.directors),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
        )
        .filter(MovieModel.id == movie_id)
        .first()
    )

    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    return MovieDetailSchema.model_validate(movie)
