from sqlalchemy import insert

from src.database.models import UserModel
from src.database.models.accounts import UserGroupModel, UserGroupEnum
from src.database.models.carts import PurchasedMovieModel, CartModel
from src.database.services.movies import get_random_movie


def test_add_movie_to_cart_if_user_unauthorized(client):
    """
    Test that user cannot add movie to cart without authentication.
    """
    movie_id = 1
    response = client.post(f"/api/v1/carts/user-cart/add-movie/?movie_id={movie_id}")
    assert (
        response.status_code == 401
    ), f"Expected status code 401 Unauthorized, but got {response.status_code}"


def test_add_unexisting_movie_to_cart(client, db_session, jwt_manager, seed_database):
    """
    Test that user cannot add unexisting movie to cart.
    """
    movie_id = 99999

    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={movie_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"


def test_user_cannot_add_to_cart_purchased_movie(
    client, db_session, jwt_manager, seed_database
):
    """
    Test that the user cannot add to the cart a movie that he previously purchased.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    movie_id = 1

    stmt = insert(PurchasedMovieModel).values(user_id=user.id, movie_id=movie_id)
    db_session.execute(stmt)
    db_session.commit()

    response = client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={movie_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 409
    ), f"Expected status code 409 Conflict, but got {response.status_code}"


def test_adding_movie_to_user_cart_success(
    client, db_session, jwt_manager, seed_database
):
    """
    Test if a movie was successfully added to the user's shopping cart.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = get_random_movie(db_session)

    response = client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()

    assert (
        "message" in response_data
    ), "Expected message: The movie has been added to user cart successfully."


def test_user_cannot_add_movie_to_cart_twice(
    client, db_session, jwt_manager, seed_database
):
    """
    Test that user cannot add movie to cart twice.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = get_random_movie(db_session)

    response = client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()

    assert (
        "message" in response_data
    ), "Expected message: The movie has been added to user cart successfully."

    second_response = client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        second_response.status_code == 400
    ), f"Expected status code 400 Bad Request, but got {response.status_code}"


def test_user_shopping_cart_when_it_is_empty(client, db_session, jwt_manager):
    """
    Test get list movies from cart, when user's shopping cart is empty.
    If user's shopping cart does not yet exist, it is created in the database for the current user.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        f"/api/v1/carts/user-cart/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    # shopping cart is not existing
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"
    response_data = response.json()
    assert (
        response_data["detail"] == "User cart is empty."
    ), f"Expected response detail: User cart is empty."

    user_cart = db_session.get(CartModel, user.id)
    assert user_cart is not None, f"Must be created user's shopping cart."
    assert (
        user_cart.cart_items == []
    ), f"User's shopping cart must be empty yet, but got {user_cart.cart_items}"

    # shopping cart is empty yet
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"
    response_data = response.json()
    assert (
        response_data["detail"] == "User cart is empty."
    ), f"Expected response detail: User cart is empty."


def test_get_user_shopping_cart_success(client, db_session, jwt_manager, seed_database):
    """
    Test get list movies from user's shopping cart successfully.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    random_movie2 = get_random_movie(db_session)
    while random_movie == random_movie2:
        random_movie2 = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie2.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    #  get user's shopping cart with 2 random movies:
    response = client.get(
        f"/api/v1/carts/user-cart/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"
    response_data = response.json()

    user_cart = db_session.get(CartModel, user.id)
    movie_ids = [item.movie_id for item in user_cart.cart_items]

    assert (
        len(response_data["cart_items"]) == len(user_cart.cart_items) == 2
    ), "Must be 2 movies in user's shopping cart."

    for item in response_data["cart_items"]:
        assert (
            item["movie_id"] in movie_ids
        ), f"User's shopping cart does not have movie_id={item['movie_id']} was not found. Should be one of {movie_ids}"

    assert (
        "name" in response_data["cart_items"][0]
    ), "User's shopping cart item does not have a 'name'"
    assert (
        "price" in response_data["cart_items"][0]
    ), "User's shopping cart item does not have a 'price'"
    assert (
        "year" in response_data["cart_items"][0]
    ), "User's shopping cart item does not have a 'year'"
    assert (
        "genres" in response_data["cart_items"][0]
    ), "User's shopping cart item does not have a 'genres'"


def test_user_cannot_update_cart_if_movie_is_not_in_cart(
    client, db_session, jwt_manager, seed_database
):
    """
    Test that user cannot update his cart:
     remove any movie from cart,
     if a specific movie is not in user's shopping cart,
     should return 404 Not Found.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    random_movie2 = get_random_movie(db_session)
    while random_movie == random_movie2:
        random_movie2 = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie2.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    random_movie3 = get_random_movie(db_session)
    while random_movie == random_movie3 or random_movie2 == random_movie3:
        random_movie2 = get_random_movie(db_session)

    #  user can remove movie, that is not in cart:
    response = client.post(
        f"/api/v1/carts/user-cart/update/?movie_id={random_movie3.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"


def test_update_user_cart_success(client, db_session, jwt_manager, seed_database):
    """
    Test that user can update his cart:
     remove any movie from cart or clear shopping cart.
    If a specific movie is not in user's shopping cart, should return 404 Not Found.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    random_movie2 = get_random_movie(db_session)
    while random_movie == random_movie2:
        random_movie2 = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie2.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    #  user can remove movie
    response = client.post(
        f"/api/v1/carts/user-cart/update/?movie_id={random_movie2.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    assert "message" in response_data, response_data
    assert (
        response_data["message"] == "User's cart has been updated successfully."
    ), "Unexpected message from user's cart update."

    # user can clear shopping cart
    clear_cart = "yes"
    response = client.post(
        f"/api/v1/carts/user-cart/update/?clear_cart={clear_cart}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    assert "message" in response_data, response_data
    assert (
        response_data["message"] == "User's cart has been cleared successfully."
    ), "Unexpected message from user's cart update."

    user_cart = db_session.get(CartModel, user.id)
    assert (
        len(user_cart.cart_items) == 0
    ), "User's cart must by empty after clear_cart='yes'"


def test_get_all_of_users_carts_allowed_only_admins(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test that all users carts can see only admins.
    """
    # group_id = 1 it is normal user
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/carts/all/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 403
    ), f"Expected status code 403 Forbidden, but got {response.status_code}"

    # if user = moderator
    user_group = (
        db_session.query(UserGroupModel)
        .filter(UserGroupModel.name == UserGroupEnum.MODERATOR)
        .first()
    )
    moderator = UserModel.create(
        email="moderator@example.com",
        raw_password="TestPassword123!",
        group_id=user_group.id,
    )
    moderator.is_active = True
    db_session.add(moderator)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": moderator.id})

    response = client.get(
        "/api/v1/carts/all/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 403
    ), f"Expected status code 403 Forbidden, but got {response.status_code}"


def test_get_all_of_users_carts_success(client, db_session, jwt_manager, seed_database):
    """
    Test getting all users carts successfully.
    """
    # user add random movie to cart
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # other_user add random movie to cart
    other_user = UserModel.create(
        email="other_test@example.com", raw_password="TestPassword123!", group_id=1
    )
    other_user.is_active = True
    db_session.add(other_user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": other_user.id})

    random_movie = get_random_movie(db_session)
    client.post(
        f"/api/v1/carts/user-cart/add-movie/?movie_id={random_movie.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    db_session.close()

    # user = admin
    user_group = (
        db_session.query(UserGroupModel)
        .filter(UserGroupModel.name == UserGroupEnum.ADMIN)
        .first()
    )
    admin = UserModel.create(
        email="admin@example.com",
        raw_password="TestPassword123!",
        group_id=user_group.id,
    )
    admin.is_active = True
    db_session.add(admin)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": admin.id})

    response = client.get(
        "/api/v1/carts/all/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"
    response_data = response.json()
    assert (
        len(response_data) == 2
    ), "List carts should have 2 items: cart of user and cart of other_user."
    assert "user_id" in response_data[0], "List cart must have 'user_id' in each cart."
    assert (
        "cart_items" in response_data[0]
    ), "List cart must have 'cart_items' in each cart."

    assert (
        "movie_id" in response_data[0]["cart_items"][0]
    ), "List cart must have 'movie_id' in each 'cart_items'."
    assert (
        "name" in response_data[0]["cart_items"][0]
    ), "List cart must have 'name' in each 'cart_items'."
    assert (
        "price" in response_data[0]["cart_items"][0]
    ), "List cart must have 'price' in each 'cart_items'."
    assert (
        "year" in response_data[0]["cart_items"][0]
    ), "List cart must have 'year' in each 'cart_items'."
    assert (
        "genres" in response_data[0]["cart_items"][0]
    ), "List cart must have 'genres' in each 'cart_items'."
