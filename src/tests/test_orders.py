from datetime import datetime, timedelta

from sqlalchemy import insert

from src.database.models import UserModel
from src.database.models.accounts import UserGroupModel, UserGroupEnum
from src.database.models.carts import PurchasedMovieModel, CartModel, CartItemModel
from src.database.models.orders import OrderModel, OrderItemModel, OrderStatusEnum
from src.database.services.movies import get_random_movie
from src.tests.conftest import db_session


def test_add_new_order_can_only_authorized_user(client):
    """
    Test that create new order can only authorized user.
    """
    response = client.post("/api/v1/orders/user/add-order/")
    assert (
        response.status_code == 401
    ), f"Expected status code 401 Unauthorized, but got {response.status_code}"


def test_add_new_order_if_user_cart_is_empty(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test that create new order cannot if user cart is empty.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})
    response = client.post(
        "/api/v1/orders/user/add-order/",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"
    response_data = response.json()
    assert "detail" in response_data, response_data
    assert response_data["detail"] == "User's cart not found or empty."


def test_add_new_order_if_any_movie_is_purchased_or_in_other_order(
    client, db_session, jwt_manager, seed_database
):
    """
    Test that if any movie from user cart is purchased or in other order,
    user cannot add this movie to cart.
    User have to see message about deleting this movie from order.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie1 = get_random_movie(db_session)

    # this movie in purchased movies table
    stmt = insert(PurchasedMovieModel).values(
        user_id=user.id, movie_id=random_movie1.id
    )
    db_session.execute(stmt)

    random_movie2 = get_random_movie(db_session)
    while random_movie1 == random_movie2:
        random_movie2 = get_random_movie(db_session)

    user_cart = CartModel(user_id=user.id)
    db_session.add(user_cart)
    db_session.flush()
    new_cart_item1 = CartItemModel(cart_id=user_cart.id, movie_id=random_movie1.id)
    new_cart_item2 = CartItemModel(cart_id=user_cart.id, movie_id=random_movie2.id)

    db_session.add(new_cart_item1)  # purchased
    db_session.add(new_cart_item2)

    db_session.commit()
    response = client.post(
        "/api/v1/orders/user/add-order/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 201
    ), f"Expected status code 201 Created, but got {response.status_code}"

    response_data = response.json()
    assert "message" in response_data, response_data
    assert (
        response_data["message"]
        == f"Movie with id={random_movie1.id} deleted from cart. Order has been created successfully."
    )
    assert (
        user_cart.cart_items == []
    ), "After creation of a order, user's cart items should be empty."

    order = db_session.get(OrderModel, user.id)

    # create new order with random_movie2 - it is in other order (not canceled)
    new_cart_item = CartItemModel(cart_id=user_cart.id, movie_id=random_movie2.id)

    db_session.add(new_cart_item)
    db_session.commit()

    response = client.post(
        "/api/v1/orders/user/add-order/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 201
    ), f"Expected status code 201 Created, but got {response.status_code}"

    assert len(user.orders) == 1, "Only one order was created."

    response_data = response.json()
    assert "message" in response_data, response_data
    assert (
        response_data["message"]
        == f"Movie with id={random_movie2.id} deleted from cart. Order has not been created."
    )
    assert (
        user_cart.cart_items == []
    ), "After creation of a order, user's cart items should be empty."


def test_add_new_order_success(client, db_session, jwt_manager, seed_database):
    """
    Test that user can create new order from user's cart successfully.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie1 = get_random_movie(db_session)
    random_movie2 = get_random_movie(db_session)
    while random_movie1 == random_movie2:
        random_movie2 = get_random_movie(db_session)

    user_cart = CartModel(user_id=user.id)
    db_session.add(user_cart)
    db_session.flush()
    new_cart_item1 = CartItemModel(cart_id=user_cart.id, movie_id=random_movie1.id)
    new_cart_item2 = CartItemModel(cart_id=user_cart.id, movie_id=random_movie2.id)

    db_session.add(new_cart_item1)
    db_session.add(new_cart_item2)

    db_session.commit()

    response = client.post(
        "/api/v1/orders/user/add-order/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 201
    ), f"Expected status code 201 Created, but got {response.status_code}"

    response_data = response.json()
    assert "message" in response_data, response_data
    assert response_data["message"] == f"Order has been created successfully."

    order = db_session.get(OrderModel, user.id)
    assert order.status == "pending", "Expected order's status should be pending."
    assert (
        order.total_amount == random_movie1.price + random_movie2.price
    ), "Expected total amount should be equal to amount of actual items prices."

    assert len(order.order_items) == 2, "Two order items must be created."
    assert order.order_items[0].movie_id in [
        random_movie1.id,
        random_movie2.id,
    ], f"Expected movie id={random_movie1.id} should be in order items."
    assert order.order_items[1].movie_id in [
        random_movie1.id,
        random_movie2.id,
    ], f"Expected movie id={random_movie2.id} should be in order items."


def test_get_list_of_all_user_orders_only_registered(client):
    """
    Test that only authorized user can see all own orders.
    """
    response = client.get("/api/v1/orders/user/all/")
    assert (
        response.status_code == 401
    ), f"Expected status code 401 Unauthorized, but got {response.status_code}"


def test_get_list_of_all_user_orders_if_are_not_any_orders(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test get list all user's orders if they are not any orders.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/orders/user/all/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"

    response_data = response.json()
    assert "detail" in response_data, response_data
    assert response_data["detail"] == "User's order not found."


def test_get_list_of_all_user_orders_success(
    client, db_session, jwt_manager, seed_database
):
    """
    Test get list all user's orders successfully.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    pending_order = OrderModel(user_id=user.id)
    db_session.add(pending_order)
    db_session.flush()
    random_movie = get_random_movie(db_session)
    order_item = OrderItemModel(
        order_id=pending_order.id,
        movie_id=random_movie.id,
        price_at_order=random_movie.price,
    )
    db_session.add(order_item)
    pending_order.total_amount = order_item.price_at_order

    paid_order = OrderModel(user_id=user.id, status=OrderStatusEnum.PAID)
    db_session.add(paid_order)
    db_session.flush()
    random_movie = get_random_movie(db_session)
    order_item = OrderItemModel(
        order_id=paid_order.id,
        movie_id=random_movie.id,
        price_at_order=random_movie.price,
    )
    db_session.add(order_item)
    paid_order.total_amount = order_item.price_at_order

    canceled_order = OrderModel(user_id=user.id, status=OrderStatusEnum.CANCELED)
    db_session.add(canceled_order)
    db_session.flush()
    random_movie = get_random_movie(db_session)
    order_item = OrderItemModel(
        order_id=canceled_order.id,
        movie_id=random_movie.id,
        price_at_order=random_movie.price,
    )
    db_session.add(order_item)
    canceled_order.total_amount = order_item.price_at_order

    db_session.commit()

    response = client.get(
        "/api/v1/orders/user/all/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert "orders" in response_data, response_data
    assert len(response_data["orders"]) == 3, "Expected 3 orders in list."

    assert (
        "id" in response_data["orders"][0]
    ), "Expected 'id' in each order of list orders."
    assert (
        "date" in response_data["orders"][0]
    ), "Expected 'date' in each order of list orders."
    assert (
        "status" in response_data["orders"][0]
    ), "Expected 'status' in each order of list orders."
    assert (
        "total_amount" in response_data["orders"][0]
    ), "Expected 'total_amount' in each order of list orders."
    assert (
        "movies" in response_data["orders"][0]
    ), "Expected 'movies' in each order of list orders."

    assert isinstance(
        response_data["orders"][0]["movies"], list
    ), "Expected 'movies' to be a list."
    assert all(
        isinstance(movie, str) for movie in response_data["orders"][0]["movies"]
    ), "Each movie should be a string."


def test_cancel_own_order_can_only_registered_user(client):
    """
    Test that cancel own order can only registered user.
    """
    response = client.post("/api/v1/orders/user/1/cancel/?to_cancel=yes")
    assert (
        response.status_code == 401
    ), f"Expected status code 401 Unauthorized, but got {response.status_code}"


def test_cancel_unexisting_order(client, db_session, jwt_manager, seed_user_groups):
    """
    Test that user cannot cancel unexisting order.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.post(
        "/api/v1/orders/user/99999/cancel/?to_cancel=yes",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"


def test_user_cannot_cancel_paid_order(client, db_session, jwt_manager, seed_database):
    """
    Test that user cannot cancel order if order is 'paid'.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    paid_order = OrderModel(
        user_id=user.id, status=OrderStatusEnum.PAID, total_amount=9.99
    )
    db_session.add(paid_order)
    db_session.commit()

    response = client.post(
        f"/api/v1/orders/user/{paid_order.id}/cancel/?to_cancel=yes",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"

    order = db_session.get(OrderModel, paid_order.user_id)
    assert order.status == "paid", "Status should be 'paid', without changes."

    response_data = response.json()
    assert "detail" in response_data, response_data
    assert (
        response_data["detail"]
        == "User's order with this ID not found or is already paid, or canceled."
    )


def test_user_cancel_order_success(client, db_session, jwt_manager, seed_database):
    """
    Test that user can cancel order successfully.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    order = OrderModel(user_id=user.id, total_amount=9.99)
    db_session.add(order)
    db_session.commit()

    assert (
        order.status == "pending"
    ), "Status of order should be 'pending', before changes."

    response = client.post(
        f"/api/v1/orders/user/{order.id}/cancel/?to_cancel=yes",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert "message" in response_data, response_data
    assert response_data["message"] == "Order has been cancelled successfully."

    assert (
        order.status == "canceled"
    ), "Status of order should be 'canceled', after changes."


def test_get_all_of_users_orders_allowed_only_admins(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test that all users orders can see only admins.
    """
    # normal user
    user_group = (
        db_session.query(UserGroupModel)
        .filter(UserGroupModel.name == UserGroupEnum.USER)
        .first()
    )
    user = UserModel.create(
        email="test@example.com",
        raw_password="TestPassword123!",
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/orders/",
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
        "/api/v1/orders/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 403
    ), f"Expected status code 403 Forbidden, but got {response.status_code}"


def test_admin_can_get_list_of_all_users_orders(
    client, db_session, jwt_manager, seed_database
):
    """
    Test that admin can get list of all users orders.
     Optional can filter by list of user_ids,
        by date: start_date - end_date and by order's status.
    """
    user1 = UserModel.create(
        email="user1@example.com", raw_password="TestPassword123!", group_id=1
    )
    user1.is_active = True
    db_session.add(user1)
    db_session.flush()

    # paid order
    user1_order = OrderModel(
        user_id=user1.id,
        total_amount=9.99,
        status=OrderStatusEnum.PAID,
        created_at=datetime.now() - timedelta(days=5),
    )
    db_session.add(user1_order)
    db_session.flush()

    user2 = UserModel.create(
        email="user2@example.com", raw_password="TestPassword123!", group_id=1
    )
    user2.is_active = True
    db_session.add(user2)
    db_session.flush()

    # canceled order
    user2_order = OrderModel(
        user_id=user2.id,
        total_amount=10.99,
        status=OrderStatusEnum.CANCELED,
        created_at=datetime.now() - timedelta(days=3),
    )
    db_session.add(user2_order)
    db_session.flush()

    admin_group = (
        db_session.query(UserGroupModel)
        .filter(UserGroupModel.name == UserGroupEnum.ADMIN)
        .first()
    )
    admin = UserModel.create(
        email="admin@example.com",
        raw_password="TestPassword123!",
        group_id=admin_group.id,
    )
    admin.is_active = True
    db_session.add(admin)
    db_session.flush()

    admin_order = OrderModel(
        user_id=admin.id,
        total_amount=11.99,
        created_at=datetime.now() - timedelta(days=1),
    )
    db_session.add(admin_order)

    db_session.commit()

    access_token = jwt_manager.create_access_token({"user_id": admin.id})

    response = client.get(
        "/api/v1/orders/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(response_data) == 3, "Expected 3 items, got {}".format(
        len(response_data)
    )

    orders_in_db = db_session.query(OrderModel).all()
    assert len(orders_in_db) == len(
        response_data
    ), "Expected that in list orders are all of orders."

    assert "id" in response_data[0], "Expected 'id' in each order of list orders."
    assert (
        "user_id" in response_data[0]
    ), "Expected 'user_id' in each order of list orders."
    assert "date" in response_data[0], "Expected 'date' in each order of list orders."
    assert (
        "status" in response_data[0]
    ), "Expected 'status' in each order of list orders."
    assert (
        "total_amount" in response_data[0]
    ), "Expected 'total_amount' in each order of list orders."
    assert (
        "movies" in response_data[0]
    ), "Expected 'movies' in each order of list orders."

    assert isinstance(
        response_data[0]["movies"], list
    ), "Expected 'movies' to be a list."
    assert all(
        isinstance(movie, str) for movie in response_data[0]["movies"]
    ), "Each movie should be a string."

    # filter by list of users ids , ex.[1,2]
    response = client.get(
        f"/api/v1/orders/?UserIdInList={user1.id},{user2.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(response_data) == 2, "Expected 2 items, got {}".format(
        len(response_data)
    )

    # filter by start_date and end_date, format: YYYY-MM-DD
    DataStartDate = str((datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"))
    DataEndDate = str(datetime.now().strftime("%Y-%m-%d"))
    response = client.get(
        f"/api/v1/orders/?DataStartDate={DataStartDate}&DataEndDate={DataEndDate}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(response_data) == 1, "Expected 1 item, got {}".format(len(response_data))
    # it's admin order
    assert (
        DataStartDate < response_data[0]["date"] < DataEndDate
    ), f"Expected dates between {DataStartDate} and {DataEndDate}."
    assert response_data[0]["user_id"] == admin.id, "Expected admin's user_id."

    # filter by order status
    status = "paid"  # order of user1
    response = client.get(
        f"/api/v1/orders/?Status={status}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(response_data) == 1, "Expected 1 item, got {}".format(len(response_data))
    assert (
        response_data[0]["status"] == status
    ), f"Expected status must be 'paid', got {response_data[0]["status"]}."
    assert response_data[0]["user_id"] == user1.id, "Expected user1's user_id."
