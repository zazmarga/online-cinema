from fastapi import FastAPI

from src.config.celery_app import celery_app
from src.routes.accounts import router as accounts_router


app = FastAPI(
    title="Online Cinema",
    description="An Online Cinema is a digital platform that allows users to select, "
    "watch, and purchase access to movies and other video materials via the internet. ",
)

api_version_prefix = "/api/v1"

app.include_router(
    accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"]
)


@app.get("/delete-expired-activation-tokens/")
async def activation_tokens_task():
    """
    Periodically delete expired activation tokens.
    The task is executed twice a day, launched using Celery-beat schedule.
    """
    task = celery_app.send_task("delete_expired_activation_tokens")
    return {"task_id": task.id}
