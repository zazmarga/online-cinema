import pytest
import random

from sqlalchemy import func, and_

from src.database.models import UserModel
from src.database.models.accounts import UserGroupEnum, UserGroupModel
from src.database.models.movies import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
)
from src.tests.conftest import jwt_manager


def test_get_movies_empty_database(db_session, client, jwt_manager):
    """
    Test that the `/movies/` endpoint returns a 404 error when the database is empty.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/movies/", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    expected_detail = {"detail": "No movies found."}
    assert (
        response.json() == expected_detail
    ), f"Expected {expected_detail}, got {response.json()}"


def test_get_movies_default_parameters(db_session, client, jwt_manager, seed_database):
    """
    Test the `/movies/` endpoint with default pagination parameters.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})
    response = client.get(
        "/api/v1/movies/", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert (
        response.status_code == 200
    ), "Expected status code 200, but got a different value"

    response_data = response.json()

    assert (
        len(response_data["movies"]) == 10
    ), "Expected 10 movies in the response, but got a different count"

    assert (
        response_data["total_pages"] > 0
    ), "Expected total_pages > 0, but got a non-positive value"

    assert (
        response_data["total_items"] > 0
    ), "Expected total_items > 0, but got a non-positive value"

    assert (
        response_data["prev_page"] is None
    ), "Expected prev_page to be None on the first page, but got a value"

    if response_data["total_pages"] > 1:
        assert (
            response_data["next_page"] is not None
        ), "Expected next_page to be present when total_pages > 1, but got None"


def test_get_movies_with_custom_parameters(
    db_session, client, jwt_manager, seed_database
):
    """
    Test the `/movies/` endpoint with custom pagination parameters.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    page = 2
    per_page = 5

    response = client.get(
        f"/api/v1/movies/?page={page}&per_page={per_page}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert (
        len(response_data["movies"]) == per_page
    ), f"Expected {per_page} movies in the response, but got {len(response_data['movies'])}"

    assert (
        response_data["total_pages"] > 0
    ), "Expected total_pages > 0, but got a non-positive value"

    assert (
        response_data["total_items"] > 0
    ), "Expected total_items > 0, but got a non-positive value"

    if page > 1:
        assert (
            response_data["prev_page"]
            == f"/movies/?page={page - 1}&per_page={per_page}"
        ), (
            f"Expected prev_page to be '/movies/?page={page - 1}&per_page={per_page}', "
            f"but got {response_data['prev_page']}"
        )

    if page < response_data["total_pages"]:
        assert (
            response_data["next_page"]
            == f"/movies/?page={page + 1}&per_page={per_page}"
        ), (
            f"Expected next_page to be '/movies/?page={page + 1}&per_page={per_page}', "
            f"but got {response_data['next_page']}"
        )
    else:
        assert (
            response_data["next_page"] is None
        ), "Expected next_page to be None on the last page, but got a value"


@pytest.mark.parametrize(
    "page, per_page, expected_detail",
    [
        (0, 10, "Input should be greater than or equal to 1"),
        (1, 0, "Input should be greater than or equal to 1"),
        (0, 0, "Input should be greater than or equal to 1"),
    ],
)
def test_invalid_page_and_per_page(
    client, page, per_page, expected_detail, db_session, jwt_manager
):
    """
    Test the `/movies/` endpoint with invalid `page` and `per_page` parameters.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        f"/api/v1/movies/?page={page}&per_page={per_page}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 422
    ), f"Expected status code 422 for invalid parameters, but got {response.status_code}"

    response_data = response.json()

    assert (
        "detail" in response_data
    ), "Expected 'detail' in the response, but it was missing"

    assert any(
        expected_detail in error["msg"] for error in response_data["detail"]
    ), f"Expected error message '{expected_detail}' in the response details, but got {response_data['detail']}"


def test_per_page_maximum_allowed_value(client, seed_database, db_session, jwt_manager):
    """
    Test the `/movies/` endpoint with the maximum allowed `per_page` value.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/movies/?page=1&per_page=20",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."
    assert (
        len(response_data["movies"]) <= 20
    ), f"Expected at most 20 movies, but got {len(response_data['movies'])}"


def test_page_exceeds_maximum(client, db_session, seed_database, jwt_manager):
    """
    Test the `/movies/` endpoint with a page number that exceeds the maximum.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    per_page = 10
    total_movies = db_session.query(MovieModel).count()
    max_page = (total_movies + per_page - 1) // per_page

    response = client.get(
        f"/api/v1/movies/?page={max_page + 1}&per_page={per_page}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 404
    ), f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()

    assert "detail" in response_data, "Response missing 'detail' field."


def test_movies_sorted_by_id_desc(client, db_session, seed_database, jwt_manager):
    """
    Test that movies are returned sorted by `id` in descending order
    and match the expected data from the database.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/movies/?page=1&per_page=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    expected_movies = (
        db_session.query(MovieModel).order_by(MovieModel.id.desc()).limit(10).all()
    )

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `id` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


def test_movie_list_with_pagination(client, db_session, seed_database, jwt_manager):
    """
    Test the `/movies/` endpoint with pagination parameters.

    Verifies the following:
    - The response status code is 200.
    - Total items and total pages match the expected values from the database.
    - The movies returned match the expected movies for the given page and per_page.
    - The `prev_page` and `next_page` links are correct.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    page = 2
    per_page = 5
    offset = (page - 1) * per_page

    response = client.get(
        f"/api/v1/movies/?page={page}&per_page={per_page}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    total_items = db_session.query(MovieModel).count()
    total_pages = (total_items + per_page - 1) // per_page
    assert response_data["total_items"] == total_items, "Total items mismatch."
    assert response_data["total_pages"] == total_pages, "Total pages mismatch."

    expected_movies = (
        db_session.query(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert expected_movie_ids == returned_movie_ids, "Movies on the page mismatch."

    assert response_data["prev_page"] == (
        f"/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    ), "Previous page link mismatch."
    assert response_data["next_page"] == (
        f"/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None
    ), "Next page link mismatch."


def test_movies_fields_match_schema(client, db_session, seed_database, jwt_manager):
    """
    Test that each movie in the response matches the fields defined in `MovieListItemSchema`.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/movies/?page=1&per_page=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."

    expected_fields = {"time", "year", "price", "id", "imdb", "name", "description"}

    for movie in response_data["movies"]:
        assert set(movie.keys()) == expected_fields, (
            f"Movie fields do not match schema. "
            f"Expected: {expected_fields}, but got: {set(movie.keys())}"
        )


def test_get_movie_by_id_not_found(client, db_session, jwt_manager):
    """
    Test that the `/movies/{movie_id}` endpoint returns a 404 error
    when a movie with the given ID does not exist.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    movie_id = 1

    response = client.get(
        f"/api/v1/movies/{movie_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 404
    ), f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()

    assert response_data == {
        "detail": "Movie with the given ID was not found."
    }, f"Expected error message not found. Got: {response_data}"


def test_get_movie_by_id_valid(client, db_session, seed_database, jwt_manager):
    """
    Test that the `/movies/{movie_id}` endpoint returns the correct movie details
    when a valid movie ID is provided.

    Verifies the following:
    - The movie exists in the database.
    - The response status code is 200.
    - The movie's `id` and `name` in the response match the expected values from the database.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    min_id = db_session.query(MovieModel.id).order_by(MovieModel.id.asc()).first()[0]
    max_id = db_session.query(MovieModel.id).order_by(MovieModel.id.desc()).first()[0]

    random_id = random.randint(min_id, max_id)

    expected_movie = (
        db_session.query(MovieModel).filter(MovieModel.id == random_id).first()
    )
    assert expected_movie is not None, "Movie not found in database."

    response = client.get(
        f"/api/v1/movies/{random_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert (
        response_data["id"] == expected_movie.id
    ), "Returned ID does not match the requested ID."

    assert (
        response_data["name"] == expected_movie.name
    ), "Returned name does not match the expected name."


def test_get_movie_by_id_fields_match_database(
    client, db_session, seed_database, jwt_manager
):
    """
    Test that the `/movies/{movie_id}` endpoint returns all fields matching the database data.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = db_session.query(MovieModel).first()
    assert random_movie is not None, "No movies found in the database."

    response = client.get(
        f"/api/v1/movies/{random_movie.id}/",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert response_data["id"] == random_movie.id, "ID does not match."
    assert response_data["uuid"] == random_movie.uuid, "Code uuid does not match."
    assert response_data["name"] == random_movie.name, "Name does not match."
    assert response_data["year"] == random_movie.year, "Year does not match."
    assert response_data["time"] == random_movie.time, "Time (duration) does not match."
    assert response_data["imdb"] == float(
        random_movie.imdb
    ), "Score imdb does not match."
    assert response_data["votes"] == random_movie.votes, "Votes does not match."
    assert (
        response_data["description"] == random_movie.description
    ), "Description does not match."
    assert response_data["price"] == float(random_movie.price), "Price does not match."

    assert response_data["gross"] == float(random_movie.gross), "Gross does not match."
    assert response_data["meta_score"] == float(
        random_movie.meta_score
    ), "Meta_score does not match."

    assert (
        response_data["certification_id"] == random_movie.certification.id
    ), "Certification ID does not match."

    expected_genres = sorted(
        [{"id": genre.id, "name": genre.name} for genre in random_movie.genres],
        key=lambda x: x["id"],
    )
    response_genres = sorted(response_data["genres"], key=lambda x: x["id"])
    assert response_genres == expected_genres, "Genres do not match."

    expected_stars = sorted(
        [{"id": star.id, "name": star.name} for star in random_movie.stars],
        key=lambda x: x["id"],
    )
    response_stars = sorted(response_data["stars"], key=lambda x: x["id"])
    assert response_stars == expected_stars, "Stars do not match."

    expected_directors = sorted(
        [
            {"id": director.id, "name": director.name}
            for director in random_movie.directors
        ],
        key=lambda x: x["id"],
    )
    response_directors = sorted(response_data["directors"], key=lambda x: x["id"])
    assert response_directors == expected_directors, "Directors do not match."


def test_create_movie_and_related_models(client, db_session, jwt_manager):
    """
    Test that a new movie is created successfully and related models
    (genres, stars, directors) are created if they do not exist.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    movie_data = {
        "name": "New Movie",
        "year": 2025,
        "time": 121,
        "imdb": 8.5,
        "votes": 111,
        "meta_score": None,
        "description": "An amazing movie.",
        "gross": 5000000.00,
        "price": 5.99,
        "certification": "S15",
        "genres": ["Action", "Adventure"],
        "stars": ["John Doe", "Jane Doe"],
        "directors": ["Frank Kapka"],
    }

    response = client.post(
        "/api/v1/movies/",
        json=movie_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 201
    ), f"Expected status code 201, but got {response.status_code}"

    response_data = response.json()

    assert response_data["id"] is not None, "ID should be generated."
    assert response_data["uuid"] is not None, "UUID should be generated."
    assert response_data["name"] == movie_data["name"], "Movie Name does not match."
    assert response_data["year"] == movie_data["year"], "Movie Year does not match."
    assert (
        response_data["time"] == movie_data["time"]
    ), "Movie Time (duration) does not match."
    assert (
        response_data["imdb"] == movie_data["imdb"]
    ), "Movie Score imdb does not match."
    assert response_data["votes"] == movie_data["votes"], "Movie Votes does not match."
    assert (
        response_data["description"] == movie_data["description"]
    ), "Movie Description does not match."
    assert response_data["price"] == movie_data["price"], "Price does not match."

    if "gross" in response_data and "gross" in movie_data:
        assert response_data["gross"] == movie_data["gross"], "Gross does not match."
    else:
        assert (
            "gross" not in response_data
        ), "Gross should not be present in response if it's not in the input data."

    if "meta_score" in response_data and "meta_score" in movie_data:
        assert (
            response_data["meta_score"] == movie_data["meta_score"]
        ), "Meta_score does not match."
    else:
        assert (
            "meta_score" not in response_data
        ), "Meta_score should not be present in response if it's not in the input data."

    for genre_name in movie_data["genres"]:
        genre = db_session.query(GenreModel).filter_by(name=genre_name).first()
        assert genre is not None, f"Genre '{genre_name}' was not created."

    for star_name in movie_data["stars"]:
        star = db_session.query(StarModel).filter_by(name=star_name).first()
        assert star is not None, f"Star '{star_name}' was not created."

    for director_name in movie_data["directors"]:
        director = db_session.query(DirectorModel).filter_by(name=director_name).first()
        assert director is not None, f"Director '{director_name}' was not created."

    certification = (
        db_session.query(CertificationModel)
        .filter_by(name=movie_data["certification"])
        .first()
    )
    assert (
        certification is not None
    ), f"Certification '{movie_data['certification']}' was not created."


def test_create_movie_duplicate_error(client, db_session, seed_database, jwt_manager):
    """
    Test that trying to create a movie with the same name and date as an existing movie
    results in a 409 conflict error.
    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    existing_movie = db_session.query(MovieModel).first()
    assert existing_movie is not None, "No existing movies found in the database."

    movie_data = {
        "name": existing_movie.name,
        "year": existing_movie.year,
        "time": existing_movie.time,
        "imdb": 8.5,
        "votes": 111,
        "meta_score": None,
        "description": "An amazing movie.",
        "gross": 5000000.00,
        "price": 5.99,
        "certification": "S15",
        "genres": ["Action", "Adventure"],
        "stars": ["John Doe", "Jane Doe"],
        "directors": ["Frank Kapka"],
    }

    response = client.post(
        "/api/v1/movies/",
        json=movie_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 409
    ), f"Expected status code 409, but got {response.status_code}"

    response_data = response.json()

    expected_detail = f"A movie with the name '{movie_data['name']}', year: '{movie_data['year']}', duration: '{movie_data['time']}' already exists."
    assert (
        response_data["detail"] == expected_detail
    ), f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"


def test_delete_movie_success_by_admin(client, db_session, seed_database, jwt_manager):
    """
    Test the `/movies/{movie_id}/` endpoint for successful movie deletion, only admins can delete it.
    """
    group = db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.ADMIN).first()
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=group.id
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    movie = db_session.query(MovieModel).first()
    assert movie is not None, "No movies found in the database to delete."

    movie_id = movie.id

    response = client.delete(
        f"/api/v1/movies/{movie_id}/",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 204
    ), f"Expected status code 204, but got {response.status_code}"

    deleted_movie = (
        db_session.query(MovieModel).filter(MovieModel.id == movie_id).first()
    )
    assert deleted_movie is None, f"Movie with ID {movie_id} was not deleted."


def test_delete_movie_not_found(client, db_session, seed_database, jwt_manager):
    """
    Test the `/movies/{movie_id}/` endpoint with a non-existent movie ID.
    """
    group = db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.ADMIN).first()
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=group.id
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    non_existent_id = 99999

    response = client.delete(
        f"/api/v1/movies/{non_existent_id}/",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 404
    ), f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert (
        response_data["detail"] == expected_detail
    ), f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"


def test_update_movie_success_by_moderator(
    client, db_session, seed_database, jwt_manager
):
    """
    Test the `/movies/{movie_id}/update-movie-info/` endpoint for successfully updating a movie's details.
    Only moderators and admins can update their details.
    """
    group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.MODERATOR).first()
    )
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=group.id
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    movie = db_session.query(MovieModel).first()
    assert movie is not None, "No movies found in the database to update."

    movie_id = movie.id
    update_data = {
        "name": "Updated Movie Name",
        "meta_score": 95.0,
    }

    response = client.patch(
        f"/api/v1/movies/{movie_id}/update-movie-info/",
        json=update_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()
    assert (
        response_data["detail"] == "Movie updated successfully."
    ), f"Expected detail message: 'Movie updated successfully.', but got: {response_data['detail']}"

    db_session.expire_all()
    updated_movie = (
        db_session.query(MovieModel).filter(MovieModel.id == movie_id).first()
    )

    assert updated_movie.name == update_data["name"], "Movie name was not updated."
    assert (
        updated_movie.meta_score == update_data["meta_score"]
    ), "Movie meta_score was not updated."


def test_update_movie_not_found(client, seed_database, db_session, jwt_manager):
    """
    Test the `/movies/{movie_id}/update-movie-info/` endpoint with a non-existent movie ID.
    """
    group = (
        db_session.query(UserGroupModel).filter_by(name=UserGroupEnum.MODERATOR).first()
    )
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=group.id
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    non_existent_id = 99999
    update_data = {"name": "Non-existent Movie", "meta_score": 90.0}

    response = client.patch(
        f"/api/v1/movies/{non_existent_id}/update-movie-info/",
        json=update_data,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 404
    ), f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert (
        response_data["detail"] == expected_detail
    ), f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"


def test_search_movies_by_genres_stars_directors(
    client, db_session, jwt_manager, seed_database
):
    """
    Test the `/api/v1/movies/search/` endpoint, which returns all movies whose genres stars & directors.

    """
    user = UserModel.create(
        email="test@mate.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    movies_query = db_session.query(MovieModel)

    param_directors = []
    check_directors = []
    directors = db_session.query(DirectorModel).all()
    if directors:
        for director in directors[:2]:
            param_directors.append(f"directors={director.name}")
            check_directors.append(director.name)

    param_genres = []
    check_genres = []
    genres = db_session.query(GenreModel).all()
    if genres:
        for genre in genres[:2]:
            param_genres.append(f"genres={genre.name}")
            check_genres.append(genre.name)

    param_stars = []
    check_stars = []
    stars = db_session.query(StarModel).all()
    if stars:
        for star in stars[:2]:
            param_stars.append(f"stars={star.name}")
            check_stars.append(star.name)

    #  only directors
    parameters = "&".join(param_directors)
    request_url = f"/api/v1/movies/search/?{parameters}"

    response = client.get(
        request_url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response_data = response.json()
    movies_query = movies_query.filter(
        MovieModel.directors.any(
            func.lower(DirectorModel.name).in_(
                [director.lower() for director in check_directors]
            )
        )
    )
    movies_list = movies_query.all()
    if len(movies_list) == 0:
        assert (
            response.status_code == 404
        ), f"Expected status code 404, but got {response.status_code}"
        assert "detail" in response_data, "Response missing 'detail' field."
    else:
        assert (
            response.status_code == 200
        ), f"Expected status code 200, but got {response.status_code}"
        assert len(movies_list) == len(
            response_data["movies"]
        ), f"{len(movies_list)} != {len(response_data["movies"])}"

    #  directors & genres
    parameters = "&".join(param_directors + param_genres)
    request_url = f"/api/v1/movies/search/?{parameters}"
    response = client.get(
        request_url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response_data = response.json()
    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    movies_query = movies_query.filter(
        and_(
            MovieModel.directors.any(
                func.lower(DirectorModel.name).in_(
                    [director.lower() for director in check_directors]
                )
            ),
            MovieModel.genres.any(
                func.lower(GenreModel.name).in_(
                    [genre.lower() for genre in check_genres]
                )
            ),
        )
    )
    movies_list = movies_query.all()
    if len(movies_list) == 0:
        assert (
            response.status_code == 404
        ), f"Expected status code 404, but got {response.status_code}"
        assert "detail" in response_data, "Response missing 'detail' field."
    else:
        assert len(movies_list) == len(
            response_data["movies"]
        ), f"{len(movies_list)} != {len(response_data["movies"])}"

    # directors, genres & stars
    parameters = "&".join(param_directors + param_genres + param_stars)
    request_url = f"/api/v1/movies/search/?{parameters}"

    response = client.get(
        request_url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response_data = response.json()

    movies_query = movies_query.filter(
        and_(
            MovieModel.directors.any(
                func.lower(DirectorModel.name).in_(
                    [director.lower() for director in check_directors]
                )
            ),
            MovieModel.genres.any(
                func.lower(GenreModel.name).in_(
                    [genre.lower() for genre in check_genres]
                )
            ),
            MovieModel.stars.any(
                func.lower(StarModel.name).in_([star.lower() for star in check_stars])
            ),
        )
    )
    movies_list = movies_query.all()
    if len(movies_list) == 0:
        assert (
            response.status_code == 404
        ), f"Expected status code 404, but got {response.status_code}"
        assert "detail" in response_data, "Response missing 'detail' field."
    else:
        assert (
            response.status_code == 200
        ), f"Expected status code 200, but got {response.status_code}"

        assert len(movies_list) == len(
            response_data["movies"]
        ), f"{len(movies_list)} != {len(response_data["movies"])}"

        response_movie_ids = [movie["movie"]["id"] for movie in response_data["movies"]]
        if len(movies_list) > 0:
            for movie in movies_list:
                assert (
                    movie.id in response_movie_ids
                ), f"{movie.id} not in {response_movie_ids}"
