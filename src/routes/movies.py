import uuid
from typing import Optional, List

from fastapi import (
    APIRouter,
    Query,
    Depends,
    HTTPException,
    status,
    Body,
    BackgroundTasks,
)
from fastapi.exceptions import ResponseValidationError
from fastapi_filter import FilterDepends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.config.dependencies import get_jwt_auth_manager, get_accounts_email_notificator
from src.database.filters.movies import MovieFilter, normalize_search_list
from src.database.models.accounts import UserGroupModel, UserModel, UserGroupEnum
from src.database.models.carts import PurchasedMovieModel, CartItemModel
from src.database.models.movies import (
    MovieModel,
    CertificationModel,
    GenreModel,
    StarModel,
    DirectorModel,
    MoviesGenresModel,
    FavoriteMovieModel,
    LikeMovieModel,
    RatingEnum,
    RatingMovieModel,
    ConfirmationEnum,
    CommentModel,
    MoviesCommentsModel,
    comment_likes,
    ReplyModel,
)
from src.database.services.movies import (
    add_movie_to_table,
    remove_movie_from_table,
    update_table_field,
    check_record_exists,
    fetch_list_favorite_movies,
)
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.notifications import EmailSenderInterface
from src.schemas.accounts import MessageResponseSchema
from src.schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
    MovieGenresUpdateSchema,
    MovieDirectorsUpdateSchema,
    MovieStarsUpdateSchema,
    MovieSearchResponseSchema,
    MovieSearchResultSchema,
    MovieGenresSchema,
    MovieDetailActionsSchema,
    MovieListFavoriteSchema,
    CommentInput,
    CommentsMovieSchema,
)
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.get(
    "/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    description=(
        "<h3>This endpoint retrieves a paginated list of movies from the database. "
        "Clients can specify the `page` number and the number of items per page using `per_page`. "
        "The response includes details about the movies, total pages, and total items, "
        "along with links to the previous and next pages if applicable.</h3>"
        "<p>Optional: can sort movies by different attributes (name, year, price, etc).</p>"
        "<p>Optional: can filer movies nameContains (movie name contains.. case-insensitive), "
        "yearOfRelease (year/list[years] of release) & "
        "IMDbRatingFrom (movies with IMDb rating greater than or equal to the specified value).</p>"
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
    sort_by: Optional[str] = Query(
        None,
        description="Sorting movies by any attribute (name, year, price, imdb, id)",
    ),
    movie_filter: Optional[MovieFilter] = FilterDepends(MovieFilter),
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Fetch a paginated list of movies from the database.

    This function retrieves a paginated list of movies, allowing the client to specify
    the page number and the number of items per page. It calculates the total pages
    and provides links to the previous and next pages when applicable.
    Optional: can sort movies by different attributes (name, year, price, etc).

    :param page: The page number to retrieve (1-based index, must be >= 1).
    :type page: int
    :param per_page: The number of items to display per page (must be between 1 and 20).
    :type per_page: int
    :param sort_by: For sorting movies by any attribute.
    :type sort_by: str
    :param movie_filter: For filtering movies by some attributes.
    :type movie_filter: FilterDepends
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

    if movie_filter:
        query = movie_filter.filter(query)

    order_by = MovieModel.default_order_by()

    if sort_by:
        query = query.order_by(sort_by)
    else:
        query = query.order_by(*order_by)

    total_items = query.count()
    movies = query.offset(offset).limit(per_page).all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]

    total_pages = (total_items + per_page - 1) // per_page

    prev_page = (
        f"/movies/movies-list/?page={page - 1}&per_page={per_page}"
        if page > 1
        else None
    )
    next_page = (
        f"/movies/movies-list/?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )

    if sort_by:
        prev_page = f"{prev_page}&sort_by={sort_by}" if prev_page is not None else None
        next_page = f"{next_page}&sort_by={sort_by}" if next_page is not None else None

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.get(
    "/search/",
    response_model=MovieSearchResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Search Movies By Directors, Genres & Stars.",
    description="Search movies based on query parameters like directors, genres, and stars.",
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with these parameters not found."}
                }
            },
        },
    },
)
def search_movies(
    directors: Optional[List[str]] = Query(
        None, description="List of directors (ex.: Steven Spielberg)"
    ),
    genres: Optional[List[str]] = Query(
        None, description="List of genres (ex.: Action, Drama)"
    ),
    stars: Optional[List[str]] = Query(
        None, description="List of stars (ex.: Tom Hanks, Al Pacino)"
    ),
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
) -> MovieSearchResultSchema:
    """
    Search movies based on query parameters like directors, genres, and stars.

    :param directors: List of directors (ex.: Steven Spielberg)
    :type directors: List[str]
    :param genres: List of genres (ex.: Action, Drama)
    :type genres: List[str]
    :param stars: List of stars (ex.: Tom Hanks, Al Pacino)
    :type stars: List[str]
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :type token: str

    :return: MovieSearchResponseSchema
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing.",
        )

    search_movies_query = db.query(MovieModel)

    if directors:
        directors = normalize_search_list(directors)
        search_movies_query = search_movies_query.filter(
            MovieModel.directors.any(DirectorModel.name.in_(directors))
        )

    if genres:
        genres = normalize_search_list(genres)
        search_movies_query = search_movies_query.filter(
            MovieModel.genres.any(GenreModel.name.in_(genres))
        )

    if stars:
        stars = normalize_search_list(stars)
        search_movies_query = search_movies_query.filter(
            MovieModel.stars.any(StarModel.name.in_(stars))
        )

    movie_list = [
        MovieSearchResponseSchema(
            movie=MovieListItemSchema(
                id=movie.id,
                name=movie.name,
                year=movie.year,
                time=movie.time,
                imdb=movie.imdb,
                description=movie.description,
                price=movie.price,
            )
        )
        for movie in search_movies_query
    ]

    if movie_list:
        return MovieSearchResultSchema(movies=movie_list)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found."
    )


@router.get(
    "/{movie_id}/",
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


@router.post(
    "/{movie_id}/",
    response_model=MovieDetailActionsSchema,
    summary="Add user-actions to movie by ID",
    description=(
        "<h3>Add some user-actions to a specific movie by its unique ID. </h3>"
        "<p>This endpoint allows to add some user-actions for the movie, such as "
        "add/delete to favorite, liked/disliked, add to user's cart, "
        "add user-comment and rate (on a 10-point scale). </p>"
        "<p>If the movie with the given "
        "ID is not found, a 404 error will be returned.</p>"
        "<p>Only for register users. If not token, a 401 error will be returned.</p>"
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
def actions_to_movie_by_id(
    movie_id: int,
    is_favorite: Optional[bool] = Query(
        None, description="Add to favorite: true, remove: false, not action: --"
    ),
    is_liked: Optional[bool] = Query(
        None, description="Add like: true, add dislike: false, not action: --"
    ),
    remove_like_dislike: ConfirmationEnum = Query(
        None, description="Remove like or dislike for this movie: yes, not action: --"
    ),
    to_rate: RatingEnum = Query(
        None, description="To rate the movie: 1 to 10, do not rate: --"
    ),
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MovieDetailActionsSchema:
    """
    Add some user-actions to a specific movie by its unique ID.

    This endpoint allows to add some user-actions for the movie, such as
    add/delete to favorite, liked/disliked, add to user's cart,
    add user-comment and rate (on a 10-point scale).
    If the movie with the given
    ID is not found, a 404 error will be returned.
    Only for register users. If not token, a 401 error will be returned.

    :param movie_id: The unique identifier of the movie to retrieve.
    :type movie_id: int
    :param is_favorite: Whether the movie is favorite or not.
    :type is_favorite: bool
    :param is_liked: Whether the movie is liked or not.
    :type is_liked: bool
    :param remove_like_dislike: Remove like or dislike for this movie.
    :type remove_like_dislike: ConfirmationEnum
    :param to_rate: To rate the movie: 1 to 10.
    type to_rate: RatingEnum
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: Token used to authenticate.
    :type token: str
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :return: The details of the requested movie.
    :rtype: MovieDetailResponseSchema

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    movie = db.query(MovieModel).filter(MovieModel.id == movie_id).first()

    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    try:
        #  is_favorite
        if is_favorite is not None:
            if not check_record_exists(
                db, user_id=user_id, movie_id=movie.id, table_name=FavoriteMovieModel
            ):
                if is_favorite is True:
                    add_movie_to_table(
                        session=db,
                        user_id=user_id,
                        movie_id=movie.id,
                        table_name=FavoriteMovieModel,
                    )
            else:
                if is_favorite is False:
                    remove_movie_from_table(
                        session=db,
                        user_id=user_id,
                        movie_id=movie.id,
                        table_name=FavoriteMovieModel,
                    )

        # is_liked
        if is_liked is not None:
            if not check_record_exists(
                db, user_id=user_id, movie_id=movie.id, table_name=LikeMovieModel
            ):
                add_movie_to_table(
                    session=db,
                    user_id=user_id,
                    movie_id=movie.id,
                    table_name=LikeMovieModel,
                )
            update_table_field(
                db,
                user_id=user_id,
                movie_id=movie.id,
                table_name=LikeMovieModel,
                table_field=LikeMovieModel.c.is_liked,
                value=is_liked,
            )

        #  remove_like_dislike
        if remove_like_dislike is not None:
            remove_movie_from_table(
                session=db,
                user_id=user_id,
                movie_id=movie.id,
                table_name=LikeMovieModel,
            )

        #  to_rate
        if to_rate is not None:
            if not check_record_exists(
                db, user_id=user_id, movie_id=movie.id, table_name=RatingMovieModel
            ):
                add_movie_to_table(
                    session=db,
                    user_id=user_id,
                    movie_id=movie.id,
                    table_name=RatingMovieModel,
                )
            update_table_field(
                db,
                user_id=user_id,
                movie_id=movie.id,
                table_name=RatingMovieModel,
                table_field=RatingMovieModel.c.rating,
                value=to_rate,
            )

    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MovieDetailActionsSchema(
        movie=movie,
        is_favorite=is_favorite,
        is_liked=is_liked,
        remove_like_dislike=remove_like_dislike,
        to_rate=to_rate,
    )


@router.post(
    "/",
    response_model=MovieDetailSchema,
    summary="Add a new movie",
    description=(
        "<h3>This endpoint allows users-MODERATOR & users-ADMIN to add a new movie to the database. "
        "It accepts details such as name, year, genres, stars, directors, and "
        "other attributes. The associated certification, genres, stars, and directors "
        "will be created or linked automatically.</h3>"
    ),
    responses={
        201: {
            "description": "Movie created successfully.",
        },
        400: {
            "description": "Invalid input.",
            "content": {
                "application/json": {"example": {"detail": "Invalid input data."}}
            },
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        403: {
            "description": "Forbidden.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to do this operation."
                    }
                }
            },
        },
    },
    status_code=201,
)
def create_movie(
    movie_data: MovieCreateSchema,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MovieDetailSchema:
    """
    Add a new movie to the database.

    This endpoint allows the creation of a new movie with details such as
    name, year, time, genres, stars, and directors. It automatically
    handles linking or creating related entities.
    Allowed only for ADMIN & MODERATOR users.

    :param movie_data: The data required to create a new movie.
    :type movie_data: MovieCreateSchema
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :type token: str
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :return: The created movie with all details.
    :rtype: MovieDetailSchema

    :raises HTTPException: Raises a 400 error for invalid input.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_group = (
        db.query(UserGroupModel).join(UserModel).filter(UserModel.id == user_id).first()
    )
    if user_group == UserGroupEnum.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do this operation.",
        )

    existing_movie = (
        db.query(MovieModel)
        .filter(
            MovieModel.name == movie_data.name,
            MovieModel.year == movie_data.year,
            MovieModel.time == movie_data.time,
        )
        .first()
    )

    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}', year: '{movie_data.year}', duration: '{movie_data.time}' already exists.",
        )

    try:
        certification = (
            db.query(CertificationModel)
            .filter_by(name=movie_data.certification)
            .first()
        )
        if not certification:
            certification = CertificationModel(name=movie_data.certification)
            db.add(certification)
            db.flush()

        genres = []
        for genre_name in movie_data.genres:
            genre = db.query(GenreModel).filter_by(name=genre_name).first()
            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                db.flush()
            genres.append(genre)

        stars = []
        for star_name in movie_data.stars:
            star = db.query(StarModel).filter_by(name=star_name).first()
            if not star:
                star = StarModel(name=star_name)
                db.add(star)
                db.flush()
            stars.append(star)

        directors = []
        for director_name in movie_data.directors:
            director = db.query(DirectorModel).filter_by(name=director_name).first()
            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                db.flush()
            directors.append(director)

        movie = MovieModel(
            uuid=str(uuid.uuid4()),
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification_id=certification.id,
            directors=directors,
            genres=genres,
            stars=stars,
        )

        db.add(movie)
        db.commit()
        db.refresh(movie)

        return MovieDetailSchema.model_validate(movie)
    except IntegrityError as e:
        print("ERROR: ", e)
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.delete(
    "/{movie_id}/",
    summary="Delete a movie by ID",
    description=(
        "<h3>Delete a specific movie from the database by its unique ID.</h3>"
        "<p>If it does not exist, a 404 error will be returned. "
        "If the movie exists, but if at least one user has purchased this movie or "
        "a movie is in users' carts, it can not be deleted, another case it can be deleted.</p>"
        "<p>Allowed only for admins and moderators. "
    ),
    responses={
        204: {
            "description": "Movie deleted successfully."
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        403: {
            "description": "Forbidden.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to do this operation."
                    }
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
    status_code=204
)
def delete_movie(
    movie_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    """
    Delete a specific movie from the database by its unique ID.

    If it does not exist, a 404 error will be returned.
    If the movie exists, but if at least one user has purchased this movie or
    a movie is in users' carts, it can not be deleted, another case it can be deleted.
    Allowed only for admins and moderators.

    :param movie_id: The unique identifier of the movie to delete.
    :type movie_id: int
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :param jwt_manager: The JWT manager used to authenticate.

    :return: A response indicating the successful deletion of the movie.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    if not user.is_admin or not user.is_moderator:
        raise HTTPException(status_code=403, detail="You don't have permission to do this operation.")

    movie = db.query(MovieModel).filter(MovieModel.id == movie_id).first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    stmt = select(PurchasedMovieModel).where(PurchasedMovieModel.c.movie_id == movie_id)
    result = db.execute(stmt).fetchall()
    if len(result) > 0:
        raise HTTPException(status_code=403, detail="You don't have permission to do this operation. At least one user has purchased this movie.")

    cart_items = db.query(CartItemModel).filter(CartItemModel.movie_id == movie_id).all()
    if len(cart_items) > 0:
        raise HTTPException(status_code=403, detail="You don't have permission to do this operation. This movie is in at least one user's cart.")

    db.delete(movie)
    db.commit()
    return {"detail": "Movie deleted successfully."}


@router.patch(
    "/{movie_id}/update-movie-info/",
    summary="Update a movie by ID",
    description=(
        "<h3>Update details of a specific movie by its unique ID.</h3>"
        "<p>This endpoint updates the details of an existing movie. If the movie with "
        "the given ID does not exist, a 404 error is returned."
        "Allowed by only moderators & admins.</p>"
    ),
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie updated successfully."}
                }
            },
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        403: {
            "description": "Forbidden.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to do this operation."
                    }
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
def update_movie(
    movie_id: int,
    movie_data: MovieUpdateSchema,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    """
    Update a specific movie by its ID.

    This function updates a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.
    Allowed only by MODERATOR-users & ADMIN-users.

    :param movie_id: The unique identifier of the movie to update.
    :type movie_id: int
    :param movie_data: The updated data for the movie.
    :type movie_data: MovieUpdateSchema
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :type token: str
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.

    :return: A response indicating the successful update of the movie.
    :rtype: None
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_group = (
        db.query(UserGroupModel).join(UserModel).filter(UserModel.id == user_id).first()
    )
    if user_group == UserGroupEnum.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do this operation.",
        )

    movie = db.query(MovieModel).filter(MovieModel.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    try:
        if movie_data.certification:
            certification = (
                db.query(CertificationModel)
                .filter_by(name=movie_data.certification)
                .first()
            )
            if not certification:
                certification = CertificationModel(name=movie_data.certification)
                db.add(certification)
                db.flush()
            del movie_data.certification
            movie.certification_id = certification.id

        for field, value in movie_data.model_dump(exclude_unset=True).items():
            setattr(movie, field, value)

        db.commit()
        db.refresh(movie)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")
    else:
        return {"detail": "Movie updated successfully."}


@router.post(
    "/{movie_id}/update-genres/",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_200_OK,
    summary="Update genres of a movie by ID",
    description=(
        "<h3>Update genres of a specific movie by its unique ID.</h3>"
        "<p>This endpoint updates genres of an existing movie. If the movie with "
        "the given ID does not exist, a 404 error is returned."
        "Allowed by only moderators & admins.</p>"
    ),
    responses={
        200: {
            "description": "Genres of movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Genres of movie updated successfully."}
                }
            },
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        403: {
            "description": "Forbidden.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to do this operation."
                    }
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
def update_movie_genres(
    movie_id: int,
    data: MovieGenresUpdateSchema,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    """
    Update genres of a specific movie by its ID.

    This function updates genres of a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.
    Allowed only by MODERATOR-users & ADMIN-users.

    :param movie_id: The unique identifier of the movie to update.
    :type movie_id: int
    :param data: The updated data for genres of a movie.
    :type data: MovieGenresUpdateSchema
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :type token: str
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.

    :return: MovieDetailSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_group = (
        db.query(UserGroupModel).join(UserModel).filter(UserModel.id == user_id).first()
    )
    if user_group == UserGroupEnum.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do this operation.",
        )

    movie = db.query(MovieModel).filter(MovieModel.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    try:
        genres = []
        for genre_name in data.genres:
            genre = db.query(GenreModel).filter_by(name=genre_name).first()
            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                db.flush()
            genres.append(genre)

        movie.genres = genres
        db.commit()
        db.refresh(movie)

        return movie

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.post(
    "/{movie_id}/update-directors/",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_200_OK,
    summary="Update directors of a movie by ID",
    description=(
        "<h3>Update directors of a specific movie by its unique ID.</h3>"
        "<p>This endpoint updates directors of an existing movie. If the movie with "
        "the given ID does not exist, a 404 error is returned."
        "Allowed by only moderators & admins.</p>"
    ),
    responses={
        200: {
            "description": "Directors of movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Directors of movie updated successfully."}
                }
            },
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        403: {
            "description": "Forbidden.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to do this operation."
                    }
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
def update_movie_directors(
    movie_id: int,
    data: MovieDirectorsUpdateSchema,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    """
    Update directors of a specific movie by its ID.

    This function updates directors of a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.
    Allowed only by MODERATOR-users & ADMIN-users.

    :param movie_id: The unique identifier of the movie to update.
    :type movie_id: int
    :param data: The updated data for directors of a movie.
    :type data: MovieDirectorsUpdateSchema
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :type token: str
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.

    :return: MovieDetailSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_group = (
        db.query(UserGroupModel).join(UserModel).filter(UserModel.id == user_id).first()
    )
    if user_group == UserGroupEnum.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do this operation.",
        )

    movie = db.query(MovieModel).filter(MovieModel.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    try:
        directors = []
        for director_name in data.directors:
            director = db.query(DirectorModel).filter_by(name=director_name).first()
            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                db.flush()
            directors.append(director)

        movie.directors = directors
        db.commit()
        db.refresh(movie)

        return movie

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.post(
    "/{movie_id}/update-stars/",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_200_OK,
    summary="Update stars of a movie by ID",
    description=(
        "<h3>Update stars of a specific movie by its unique ID.</h3>"
        "<p>This endpoint updates stars of an existing movie. If the movie with "
        "the given ID does not exist, a 404 error is returned."
        "Allowed by only moderators & admins.</p>"
    ),
    responses={
        200: {
            "description": "Stars of movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Stars of movie updated successfully."}
                }
            },
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        403: {
            "description": "Forbidden.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You don't have permission to do this operation."
                    }
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
def update_movie_stars(
    movie_id: int,
    data: MovieStarsUpdateSchema,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    """
    Update stars of a specific movie by its ID.

    This function updates stars of a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.
    Allowed only by MODERATOR-users & ADMIN-users.

    :param movie_id: The unique identifier of the movie to update.
    :type movie_id: int
    :param data: The updated data for stars of a movie.
    :type data: MovieStarsUpdateSchema
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :type token: str
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.

    :return: MovieDetailSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user_group = (
        db.query(UserGroupModel).join(UserModel).filter(UserModel.id == user_id).first()
    )
    if user_group == UserGroupEnum.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do this operation.",
        )

    movie = db.query(MovieModel).filter(MovieModel.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    try:
        stars = []
        for star_name in data.stars:
            star = db.query(StarModel).filter_by(name=star_name).first()
            if not star:
                star = StarModel(name=star_name)
                db.add(star)
                db.flush()
            stars.append(star)

        movie.stars = stars
        db.commit()
        db.refresh(movie)

        return movie

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get(
    "/sort/by-genres/",
    response_model=List[MovieGenresSchema],
    status_code=status.HTTP_200_OK,
    summary="Get list of genres with count of movies",
    description=("<h3>Get list of genres with count of movies in each genre.</h3>"),
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {"example": {"detail": "User unauthorized."}}
            },
        },
        404: {
            "description": "Genres not found.",
            "content": {
                "application/json": {"example": {"detail": "Genres not found."}}
            },
        },
    },
)
def get_genres_list_with_count_of_movie(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
) -> List[MovieGenresSchema]:
    """
    Get list of genres with count of movies in each genre.

    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param token: The token used to authenticate.
    :type token: str

    :return: MovieGenresListSchema
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing.",
        )

    genres = (
        db.query(GenreModel, func.count(MovieModel.id).label("movie_count"))
        .select_from(GenreModel)
        .join(MoviesGenresModel, MoviesGenresModel.c.genre_id == GenreModel.id)
        .join(MovieModel, MovieModel.id == MoviesGenresModel.c.movie_id)
        .group_by(GenreModel.id)
        .all()
    )

    if not genres:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Genres not found."
        )

    genres_list = [
        MovieGenresSchema(genre=genre, count_of_movies=movie_count)
        for genre, movie_count in genres
    ]

    return genres_list


@router.get(
    "/user/favorite-movies/",
    response_model=MovieListFavoriteSchema,
    summary="Get a list favorite movies",
    description=(
        "<h3>This endpoint retrieves a list of favorite movies from the database. </h3>"
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
def get_list_favorite_movies(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MovieListFavoriteSchema:
    """
    Fetch a list of favorite movies from the database.

    :param token: Token used to authenticate.
    :type token: str
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :return: A response containing the list of favorite movies and metadata.
    :rtype: MovieListResponseSchema

    :raises HTTPException: Raises a 401 if user unauthorized. Raises a 404 error if no movies are found for the requested page.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    list_favorite_movies = fetch_list_favorite_movies(session=db, user_id=user_id)

    if not list_favorite_movies:
        raise HTTPException(status_code=404, detail="No favorite movies found.")

    return MovieListFavoriteSchema(movies=list_favorite_movies)


@router.post(
    "/{movie_id}/comments/add/",
    response_model=MessageResponseSchema,
    summary="Add comment to movies by ID.",
    description=("<h3>This endpoint allows to add comment to movie using it ID.</h3>"),
    responses={
        400: {
            "description": "Bad request.",
            "content": {
                "application/json": {"example": {"detail": "Invalid input data."}}
            },
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {"detail": "Authorization header is missing."}
                }
            },
        },
    },
    status_code=status.HTTP_201_CREATED,
)
def add_comment_to_movie(
    movie_id: int,
    comment_input: CommentInput = Body(..., example={"content": ""}),
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema:
    """
    This endpoint allows to add comment to movie using it ID.

    :param movie_id: The movie ID.
    :type movie_id: int
    :param comment_input: Content of the comment.
    :type comment_input: CommentInput
    :param token: Token used to authenticate.
    :type token: str
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :return: MessageResponseSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if not comment_input.content or not comment_input.content.strip():
        raise HTTPException(
            status_code=400,
            detail="Content of the comment not be empty.",
        )

    try:
        new_comment = CommentModel(content=comment_input.content, user_id=user_id)
        db.add(new_comment)
        db.flush()

        record = MoviesCommentsModel.insert().values(
            user_id=user_id,
            movie_id=movie_id,
            comment_id=new_comment.id,
        )
        db.execute(record)
        db.commit()

        return MessageResponseSchema(message="The comment was added successfully.")

    except (IntegrityError, ResponseValidationError):
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get(
    "/{movie_id}/comments/",
    response_model=CommentsMovieSchema,
    summary="Get list comments by movie ID.",
    description=("<h3>This endpoint show all comments for movie by ID.</h3>"),
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
            "description": "No comments found.",
            "content": {
                "application/json": {
                    "example": {"detail": "This movie does not have comments yet."}
                }
            },
        },
    },
    status_code=status.HTTP_200_OK,
)
def get_list_comments_for_movie(
    movie_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
) -> CommentsMovieSchema:
    """
    Get list comments for movie by ID.

    :param movie_id: The movie ID.
    :type movie_id: int
    :param token: Token used to authenticate.
    :type token: str
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session

    :return: CommentsMovieSchema
    """

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing.",
        )

    comments = (
        db.query(CommentModel)
        .join(MoviesCommentsModel, MoviesCommentsModel.c.comment_id == CommentModel.id)
        .filter(MoviesCommentsModel.c.movie_id == movie_id)
        .all()
    )
    if not comments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This movie does not have comments yet.",
        )

    movie = db.query(MovieModel).get(movie_id)

    return CommentsMovieSchema(movie=movie, comments=comments)


@router.post(
    "/{movie_id}/comments/actions/",
    response_model=MessageResponseSchema,
    summary="Add like or reply to comment for movies by ID.",
    description=(
        "<h3>This endpoint allows to add like or reply to comment for movies by ID.</h3>"
        "<p> After that,  owner of comment get email-notification.</p>"
    ),
    responses={
        400: {
            "description": "Bad request.",
            "content": {
                "application/json": {"example": {"detail": "Invalid input data."}}
            },
        },
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {"detail": "Authorization header is missing."}
                }
            },
        },
        404: {
            "description": "No comment found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Comment with comment_id does not exist for this movie."
                    }
                }
            },
        },
    },
    status_code=status.HTTP_201_CREATED,
)
def add_reply_like_to_comment_for_movie(
    movie_id: int,
    comment_id: int,
    background_tasks: BackgroundTasks,
    is_liked: Optional[bool] = None,
    reply_input: CommentInput = Body(..., example={"content": ""}),
    db: Session = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> MessageResponseSchema:
    """
    This endpoint allows to add comment to movie using it ID.

    :param movie_id: The movie ID.
    :type movie_id: int
    :param comment_id: The movie comment ID.
    :type comment_id: int
    :param is_liked: For like or clear like the movie.
    :type is_liked: bool
    :param reply_input: Content of the replay for comment.
    :type reply_input: CommentInput
    :param email_sender: Email sender. For email notification about actions.
    :type email_sender: EmailSenderInterface
    :param token: Token used to authenticate.
    :type token: str
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: Session
    :param jwt_manager: The JWT manager used to authenticate.
    :type jwt_manager: JWTAuthManagerInterface

    :return: MessageResponseSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if not comment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input data."
        )

    owner_of_comment = (
        db.query(MoviesCommentsModel.c.user_id)
        .filter(
            MoviesCommentsModel.c.comment_id == comment_id,
            MoviesCommentsModel.c.movie_id == movie_id,
        )
        .first()
    )

    if not owner_of_comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not found this comment.",
        )

    try:
        if is_liked is not None:
            existing_like = db.execute(
                comment_likes.select().where(
                    comment_likes.c.user_id == user_id,
                    comment_likes.c.comment_id == comment_id,
                )
            ).fetchone()

            if existing_like is None:
                if is_liked is True:
                    add_like = comment_likes.insert().values(
                        user_id=user_id, comment_id=comment_id
                    )
                    db.execute(add_like)
                    db.commit()
            else:
                if is_liked is False:
                    record_like = comment_likes.delete().where(
                        comment_likes.c.user_id == user_id,
                        comment_likes.c.comment_id == comment_id,
                    )
                    db.execute(record_like)
                    db.commit()

        if reply_input.content:
            new_reply = ReplyModel(
                content=reply_input.content, comment_id=comment_id, user_id=user_id
            )
            db.add(new_reply)
            db.commit()
            db.refresh(new_reply)

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    user_owner_of_comment = (
        db.query(UserModel).filter(UserModel.id == owner_of_comment.user_id).first()
    )
    comment_link = f"http://127.0.0.1:8000/movies/{movie_id}/comments/actions/?comment_id={comment_id}"
    email_message = f"Your {comment_id=} for {movie_id=} has been liked or replied to by {user_id=}."
    background_tasks.add_task(
        email_sender.send_like_reply_notification_email,
        str(user_owner_of_comment.email),
        comment_link,
        email_message,
    )

    return MessageResponseSchema(message="The like/comment was added successfully.")
