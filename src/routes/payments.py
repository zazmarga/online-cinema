import os

import stripe
from fastapi import (
    APIRouter,
    Request,
    HTTPException,
    Depends,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config.settings import BaseAppSettings
from src.config.dependencies import get_settings, get_jwt_auth_manager
from src.database.models import UserModel
from src.database.models.carts import PurchasedMovieModel
from src.database.models.orders import OrderModel, OrderStatusEnum
from src.database.models.payments import PaymentModel, PaymentItemModel
from src.database.services.payments import check_prices_of_order_items
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.schemas.accounts import MessageResponseSchema
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface

router = APIRouter()
api_prefix = "/api/v1/payments"


@router.get("/success/")
def success_page():
    return {"message": "Payment was successful!"}


@router.get("/cancel/")
def cancel_page():
    return {"message": "Payment was canceled."}


@router.get(
    "/{order_id}/confirm-and-pay/", responses={}, status_code=status.HTTP_303_SEE_OTHER
)
async def confirm_order_and_create_checkout_session(
    order_id: int,
    settings: BaseAppSettings = Depends(get_settings),
    # token: str = Depends(get_token),
    db: Session = Depends(get_db),
    # jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> RedirectResponse or MessageResponseSchema:
    """
    Confirm user order. Create checkout session.
    This endpoint allows to confirm user order by order ID and create checkout session for payment.

    :return: RedirectResponse
    """

    # try:
    #     payload = jwt_manager.decode_access_token(token)
    #     user_id = payload.get("user_id")
    # except BaseSecurityError as e:
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    user_id = 1

    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    order = (
        db.query(OrderModel)
        .filter(OrderModel.id == order_id, OrderModel.user_id == user_id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User's order with this ID not found.",
        )

    #  Check prices of order_items (maybe its were changed)
    total_amount = check_prices_of_order_items(db, order_id)

    # session for payment
    stripe.api_key = settings.STRIPE_SECRET_KEY

    checkout_session = stripe.checkout.Session.create(
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Order Online Cinema",
                    },
                    "unit_amount": int(total_amount * 100),
                },
                "quantity": 1,
            }
        ],
        metadata={
            "user_id": user_id,
            "email": user.email,
            "request_id": f"{user_id}-{order_id}-{os.urandom(4).hex()}",
        },
        mode="payment",
        success_url=settings.BASE_URL + api_prefix + "/success/",
        cancel_url=settings.BASE_URL + api_prefix + "/cancel/",
        customer_email=user.email,
    )

    print(
        f"{checkout_session.id=}: {checkout_session.status=}, {checkout_session.url=}"
    )
    return RedirectResponse(checkout_session.url, status_code=303)


@router.post("/webhook/")
async def stripe_webhook(
    request: Request,
    settings: BaseAppSettings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    """
    This endpoint is used to check transactions via webhooks provided by the payment system.
    Updates the order status after a successful payment.
    Adds a new payment to the database (and payment items).
    Sends an email to the user informing them of a successful payment.

    :param request:
    :param settings:
    :param db:
    :return:
    """
    # get payload
    payload = await request.body()

    # get Stripe-Signature
    signature_header = request.headers.get("Stripe-Signature")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    webhook_secret = settings.WEBHOOK_SECRET

    # check Signature
    try:
        event = stripe.Webhook.construct_event(
            payload, signature_header, webhook_secret
        )
        print("Webhook verified!")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except ValueError as e:
        print("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")

    # if event - checkout.session.completed
    if event["type"] == "checkout.session.completed":
        payment = event["data"]["object"]

        amount = payment["amount_total"] / 100
        user_id = payment["metadata"]["user_id"]
        order_id = int(payment["metadata"]["request_id"].split("-")[1])
        user_email = payment["customer_details"]["email"]
        user_name = payment["customer_details"]["name"]
        external_payment_id = payment["id"]

        # add new_payment and payment_items, save in db
        try:
            new_payment = PaymentModel(
                user_id=user_id,
                order_id=order_id,
                amount=amount,
                external_payment_id=external_payment_id,
            )
            db.add(new_payment)
            db.flush()
            # change order.status - PAID
            order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
            order.status = OrderStatusEnum.PAID
            for order_item in order.order_items:
                new_payment_item = PaymentItemModel(
                    payment_id=new_payment.id,
                    order_item_id=order_item.id,
                    price_at_payment=order_item.movie.price,
                )
                db.add(new_payment_item)

                # and to table - purchased movies
                stmt = insert(PurchasedMovieModel).values(
                    user_id=user_id, movie_id=order_item.movie.id
                )
                db.execute(stmt)
                db.flush()
            db.commit()
            db.refresh(new_payment)

            # send email about successful payment
            # send_email_background_task(user_email, order_id)
            print(f"{user_email=}")
            print(f"{user_name=}")

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {}
