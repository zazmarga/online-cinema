import json

import stripe
from fastapi import APIRouter, responses, Request, HTTPException, Depends

from src.config.settings import BaseAppSettings
from src.config.dependencies import get_settings

router = APIRouter()


@router.get("/success/")
async def success_page():
    return {"message": "Payment was successful!"}


@router.get("/cancel/")
async def cancel_page():
    return {"message": "Payment was canceled."}


@router.get("/checkout/{order_id}/")
async def create_checkout_session(
    order_id: int,
    settings: BaseAppSettings = Depends(get_settings),
):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    checkout_session = stripe.checkout.Session.create(
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "FastAPI Stripe Checkout",
                    },
                    "unit_amount": amount * 100,
                },
                "quantity": 1,
            }
        ],
        metadata={"user_id": 3, "email": "abc@gmail.com", "request_id": 1234567890},
        mode="payment",
        success_url=settings.BASE_URL + "/success/",
        cancel_url=settings.BASE_URL + "/cancel/",
        customer_email="ping@fastapitutorial.com",
    )
    return responses.RedirectResponse(checkout_session.url, status_code=303)


@router.post("/webhook/")
async def stripe_webhook(
    request: Request, settings: BaseAppSettings = Depends(get_settings)
):
    payload = await request.body()
    event = None

    try:
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except ValueError as e:
        print("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    print("event received is", event)
    if event["type"] == "checkout.session.completed":
        payment = event["data"]["object"]
        amount = payment["amount_total"]
        currency = payment["currency"]
        user_id = payment["metadata"]["user_id"]  # get custom user id from metadata
        user_email = payment["customer_details"]["email"]
        user_name = payment["customer_details"]["name"]
        order_id = payment["id"]
        # save to db
        # send email in background task
    return {}
