import os
from datetime import datetime, timedelta

from src.database.models import UserModel
from src.database.models.accounts import UserGroupModel, UserGroupEnum
from src.database.models.orders import OrderModel, OrderStatusEnum, OrderItemModel
from src.database.models.payments import PaymentModel, PaymentStatusEnum
from src.database.services.movies import get_random_movie


def test_confirm_order_can_registered_user(client):
    """
    Test that only register user can confirm own order and get checkout session for pay it.
    """
    response = client.get("/api/v1/payments/1/confirm-and-pay/")
    assert (
        response.status_code == 401
    ), f"Expected status code 401 Unauthorized, but got {response.status_code}"


def test_confirm_unexisting_order(client, db_session, jwt_manager, seed_user_groups):
    """
    Test that  user cannot confirm unexisting order and get checkout session for pay it.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/payments/99999/confirm-and-pay/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"

    response_data = response.json()
    assert "detail" in response_data, response_data
    assert response_data["detail"] == "User's order with this ID not found."


def test_confirm_paid_or_canceled_order(client, db_session, jwt_manager, seed_database):
    """
    Test that user cannot confirm paid or canceled order and get checkout session for pay it.
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
    db_session.flush()
    canceled_order = OrderModel(
        user_id=user.id, status=OrderStatusEnum.CANCELED, total_amount=13.99
    )
    db_session.add(canceled_order)
    db_session.commit()

    response = client.get(
        f"/api/v1/payments/{paid_order.id}/confirm-and-pay/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 400
    ), f"Expected status code 400 Bad Request, but got {response.status_code}"

    response_data = response.json()
    assert "detail" in response_data, response_data
    assert response_data["detail"] == "Payment was paid or canceled."

    response = client.get(
        f"/api/v1/payments/{canceled_order.id}/confirm-and-pay/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 400
    ), f"Expected status code 400 Bad Request, but got {response.status_code}"

    response_data = response.json()
    assert "detail" in response_data, response_data
    assert response_data["detail"] == "Payment was paid or canceled."


def test_confirm_order_if_price_of_movie_was_changed(
    client, db_session, jwt_manager, seed_database
):
    """
    Test that total_amount in order and price_at_order in item_order will be updated with actual price.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    random_movie = get_random_movie(db_session)

    order = OrderModel(user_id=user.id, total_amount=random_movie.price)
    db_session.add(order)
    db_session.flush()

    order_item = OrderItemModel(
        order_id=order.id,
        movie_id=random_movie.id,
        price_at_order=random_movie.price,
    )
    db_session.add(order_item)

    random_movie.price = random_movie.price * 2

    db_session.commit()

    client.get(
        f"/api/v1/payments/{order.id}/confirm-and-pay/",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert (
        order.total_amount == random_movie.price
    ), "Total amount should be updated with actual price."
    assert (
        order_item.price_at_order == random_movie.price
    ), "Item price should be updated with actual price."


def test_get_list_payments_can_registered_user(client):
    """
    Test that only register user can get list own payments.
    """
    response = client.get("/api/v1/payments/user/all/")
    assert (
        response.status_code == 401
    ), f"Expected status code 401 Unauthorized, but got {response.status_code}"


def test_get_list_user_payments_if_there_are_not(client, db_session, jwt_manager):
    """
    Test get list user's payments when there are no payments.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.commit()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    response = client.get(
        "/api/v1/payments/user/all/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 404
    ), f"Expected status code 404 Not Found, but got {response.status_code}"

    response_data = response.json()
    assert "detail" in response_data, response_data
    assert response_data["detail"] == "User's payments not found."


def test_get_list_user_payments_success(client, db_session, jwt_manager):
    """
    Test get list user's payments successfully.
    """
    user = UserModel.create(
        email="test@example.com", raw_password="TestPassword123!", group_id=1
    )
    user.is_active = True
    db_session.add(user)
    db_session.flush()
    access_token = jwt_manager.create_access_token({"user_id": user.id})

    user_payment = PaymentModel(
        user_id=user.id,
        order_id=1,
        amount=9.99,
        external_payment_id=str(os.urandom(16)),
    )
    db_session.add(user_payment)

    other_user = UserModel.create(
        email="other@example.com", raw_password="TestPassword123!", group_id=1
    )
    other_user.is_active = True
    db_session.add(other_user)
    db_session.flush()
    other_user_payment = PaymentModel(
        user_id=other_user.id,
        order_id=2,
        amount=15.55,
        external_payment_id=str(os.urandom(16)),
    )
    db_session.add(other_user_payment)

    db_session.commit()

    payments = db_session.query(PaymentModel).all()

    response = client.get(
        "/api/v1/payments/user/all/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(payments) != len(
        response_data["payments"]
    ), "Expected not all payments, only user's payments in list."

    assert (
        "id" in response_data["payments"][0]
    ), "Expected payment 'id' in each item of payments."
    assert (
        "date" in response_data["payments"][0]
    ), "Expected payment 'date' in each item of payments."
    assert (
        "amount" in response_data["payments"][0]
    ), "Expected payment 'amount' in each item of payments."
    assert (
        "status" in response_data["payments"][0]
    ), "Expected payment 'status' in each item of payments."

    assert response_data["payments"][0]["amount"] == float(user_payment.amount)
    assert response_data["payments"][0]["status"] == "successful"


def test_only_admin_can_get_list_payments_all_users(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test that only admin can get list payments for all users.
    """
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
        "/api/v1/payments/",
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
        "/api/v1/payments/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 403
    ), f"Expected status code 403 Forbidden, but got {response.status_code}"


def test_admin_can_get_list_of_all_users_payments(
    client, db_session, jwt_manager, seed_user_groups
):
    """
    Test that admin can get list of all users payments.
     Optional can filter by list of user_ids,
        by date: start_date - end_date and by payment's status.
    """
    user1 = UserModel.create(
        email="user1@example.com", raw_password="TestPassword123!", group_id=1
    )
    user1.is_active = True
    db_session.add(user1)
    db_session.flush()

    # user1 payment
    user1_payment = PaymentModel(
        user_id=user1.id,
        order_id=1,
        amount=9.99,
        external_payment_id=str(os.urandom(16)),
        created_at=datetime.now() - timedelta(days=5),
    )
    db_session.add(user1_payment)
    db_session.flush()

    user2 = UserModel.create(
        email="user2@example.com", raw_password="TestPassword123!", group_id=1
    )
    user2.is_active = True
    db_session.add(user2)
    db_session.flush()

    # user2 payment
    user2_payment = PaymentModel(
        user_id=user2.id,
        order_id=2,
        amount=15.99,
        external_payment_id=str(os.urandom(16)),
        status=PaymentStatusEnum.CANCELED,
        created_at=datetime.now() - timedelta(days=3),
    )
    db_session.add(user2_payment)
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

    # admin payment
    admin_payment = PaymentModel(
        user_id=admin.id,
        order_id=3,
        amount=20.99,
        external_payment_id=str(os.urandom(16)),
        created_at=datetime.now() - timedelta(days=1),
    )
    db_session.add(admin_payment)

    db_session.commit()

    access_token = jwt_manager.create_access_token({"user_id": admin.id})

    response = client.get(
        "/api/v1/payments/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(response_data) == 3, "Expected 3 items, got {}".format(
        len(response_data)
    )

    payments_in_db = db_session.query(PaymentModel).all()
    assert len(payments_in_db) == len(
        response_data
    ), "Expected that in list payments are all of payments in db."

    assert "id" in response_data[0], "Expected 'id' in each payment of list payments."
    assert (
        "user_id" in response_data[0]
    ), "Expected 'user_id' in each payment of list payments."
    assert (
        "date" in response_data[0]
    ), "Expected 'date' in each payment of list payments."
    assert (
        "status" in response_data[0]
    ), "Expected 'status' in each payment of list payments."
    assert (
        "amount" in response_data[0]
    ), "Expected 'amount' in each payment of list payments."

    # filter by list of users ids , ex.[1,2]
    response = client.get(
        f"/api/v1/payments/?UserIdInList={user1.id},{user2.id}",
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
        f"/api/v1/payments/?DataStartDate={DataStartDate}&DataEndDate={DataEndDate}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(response_data) == 1, "Expected 1 item, got {}".format(len(response_data))

    assert (
        DataStartDate < response_data[0]["date"] < DataEndDate
    ), f"Expected dates between {DataStartDate} and {DataEndDate}."
    assert response_data[0]["user_id"] == admin.id, f"Expected user_id = {admin.id}."

    # filter by payment status
    status = "canceled"  # payment of user2
    response = client.get(
        f"/api/v1/payments/?Status={status}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 200
    ), f"Expected status code 200 OK, but got {response.status_code}"

    response_data = response.json()
    assert len(response_data) == 1, "Expected 1 item, got {}".format(len(response_data))
    assert (
        response_data[0]["status"] == status
    ), f"Expected status must be 'canceled', got {response_data[0]["status"]}."
    assert response_data[0]["user_id"] == user2.id, f"Expected user_id = {user2.id}."
