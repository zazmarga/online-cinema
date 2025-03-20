from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/user-cart/",
)
def user_cart():
    return {"cart": []}
