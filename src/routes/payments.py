import os
from typing import List, Optional

import stripe
from fastapi import (
    APIRouter,
    Request,
    HTTPException,
    Depends,
    status,
    BackgroundTasks,
)
from fastapi.responses import RedirectResponse
from fastapi_filter import FilterDepends
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.testing.pickleable import User

from src.config.settings import BaseAppSettings
from src.config.dependencies import (
    get_settings,
    get_jwt_auth_manager,
    get_accounts_email_notificator,
)
from src.database.filters.payments import PaymentFilter
from src.database.models import UserModel
from src.database.models.carts import PurchasedMovieModel
from src.database.models.orders import OrderModel, OrderStatusEnum
from src.database.models.payments import PaymentModel, PaymentItemModel
from src.database.services.payments import check_prices_of_order_items
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.notifications import EmailSenderInterface
from src.schemas.accounts import MessageResponseSchema
from src.schemas.payments import PaymentListSchema, PaymentItemListSchema, PaymentListFullSchema
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
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> RedirectResponse or MessageResponseSchema:
    """
    Confirm user order. Create checkout session.
    This endpoint allows to confirm user order by order ID and create checkout session for payment.

    :return: RedirectResponse
    """

    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

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

    if order.status == OrderStatusEnum.PAID or order.status == OrderStatusEnum.CANCELED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Payment was paid or canceled."
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
    background_tasks: BackgroundTasks,
    settings: BaseAppSettings = Depends(get_settings),
    db: Session = Depends(get_db),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    """
    This endpoint is used to check transactions via webhooks provided by the payment system.
    Updates the order status after a successful payment.
    Adds a new payment to the database (and payment items).
    Sends an email to the user informing them of a successful payment.

    :param request:
    :param background_tasks:
    :param settings:
    :param db:
    :param email_sender:

    :return:
    """
    # get payload
    payload = await request.body()

    # get Stripe-Signature
    signature_header = request.headers.get("Stripe-Signature")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    webhook_secret = settings.WEBHOOK_SECRET

    # # check Signature
    # try:
    #     event = stripe.Webhook.construct_event(
    #         payload, signature_header, webhook_secret
    #     )
    #     print("Webhook verified!")
    # except stripe.error.SignatureVerificationError:
    #     raise HTTPException(status_code=400, detail="Invalid signature")
    # except ValueError as e:
    #     print("Invalid payload")
    #     raise HTTPException(status_code=400, detail="Invalid payload")
    try:
        # check Signature Webhook
        event = stripe.Webhook.construct_event(
            payload, signature_header, webhook_secret
        )
        print("Webhook verified!")

        if event['type'] == 'invoice.payment_failed':
            # Payment failed
            invoice = event['data']['object']
            payment_intent = invoice.get('payment_intent')

            if payment_intent:
                try:
                    intent = stripe.PaymentIntent.retrieve(payment_intent)

                    if intent.status == "requires_payment_method":
                        print("Payment failed: The payment method was declined.")
                        error_message = "The payment was declined. Please try a different payment method."
                        print(f"Recommendation: {error_message}")
                    else:
                        print("Other error occurred.")
                except stripe.error.CardError as e:
                    body = e.json_body
                    err = body.get("error", {})
                    error_message = err.get("message")
                    print(f"Card Error: {error_message}")
                    user_message = "Your card was declined. Please check your card details or try a different card."
                    print(f"Recommendation: {user_message}")
                except Exception as e:
                    print(f"General error: {e}")
        else:
            print(f"Unhandled event type: {event['type']}")

    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except ValueError as e:
        print("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

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

            # send email: payment confirmation
            payments_link = "http://127.0.0.1:8000/payments/user/all/"
            email_message = (
                f"Payment in the amount of ${amount} was received from {user_name}."
            )
            background_tasks.add_task(
                email_sender.send_payment_confirmation_email,
                str(user_email),
                payments_link,
                email_message,
            )

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {}


@router.get(
    "/user/all/",
    response_model=PaymentListSchema,
    summary="Get list of all user's payments.",
    description="This endpoint shows list of all user's payments.",
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authorization header is missing or Invalid token."
                    }
                }
            },
        },
        404: {
            "description": "Not found.",
            "content": {
                "application/json": {"example": {"detail": "User's payments not found."}}
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while getting users orders."
                    }
                }
            },
        },
    },
)
def get_list_user_payments(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> PaymentListSchema:
    """
    Get list of payments.
    This endpoint shows list of all user's payments.

    :return: PaymentListSchema
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    payments = db.query(PaymentModel).filter(PaymentModel.user_id == user_id).all()

    if not payments:
        raise HTTPException(status_code=404, detail="User's payments not found.")

    response_payments = []

    for payment in payments:
        response_payments.append(
            PaymentItemListSchema(
                id=payment.id,
                date=payment.created_at.strftime("%Y-%m-%d %H:%M"),
                amount=payment.amount,
                status=payment.status
            )
        )

    return PaymentListSchema(payments=response_payments)


@router.get(
    "/",
    response_model=List[PaymentListFullSchema],
    summary="Get list of all payments.",
    description="<h3>This endpoint shows list of all payments for all users. Allowed only for ADMIN users. </h3>"
                "<p>Optional:  Filtering payments by user_id/list(user_id), ex.: 2,3; <br>"
                "by start date (inclusive), ex.: YYYY-MM-DD; <br>"
                "by end date (inclusive), ex.: YYYY-MM-DD; <br>"
                "by status, ex.: successful  (should be one of: 'successful', 'refunded' or 'canceled').</p>",
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "description": "Unauthorized.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authorization header is missing or Invalid token."
                    }
                }
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
            "description": "Not found.",
            "content": {
                "application/json": {"example": {"detail": "Users payments not found."}}
            },
        },
        500: {
            "description": "Internal Server Error.",
            "content": {
                "application/json": {
                    "example": {"detail": "An error occurred while getting orders."}
                }
            },
        },
    },
)
def get_list_payments(
    payment_filter: Optional[PaymentFilter] = FilterDepends(PaymentFilter),
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> List[PaymentListFullSchema]:
    """
    Get list of all payments.
    This endpoint shows list of all payments for all users. Allowed only for ADMIN users.
    Optional:  Filtering payments
    by user_id/list(user_id), ex.: 2,3;
    by start date (inclusive), ex.: YYYY-MM-DD;
    by end date (inclusive), ex.: YYYY-MM-DD;
    by status, ex.: successful  (should be one of: 'successful', 'refunded' or 'canceled').

    :param payment_filter: PaymentFilter - filtering payments
    :return: List[PaymentListFullSchema]
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to do this operation.")

    query = db.query(PaymentModel)

    if payment_filter:
        query = payment_filter.filter(query)

    payments = query.all()

    if not payments:
        raise HTTPException(status_code=404, detail="User's payments not found.")

    response_payments = []

    for payment in payments:
        response_payments.append(
            PaymentListFullSchema(
                id=payment.id,
                user_id=payment.user_id,
                date=payment.created_at.strftime("%Y-%m-%d %H:%M"),
                amount=payment.amount,
                status=payment.status,
            )
        )

    return response_payments