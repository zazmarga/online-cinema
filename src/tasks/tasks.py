from datetime import datetime, timezone
from typing import cast, Union

from src.config.celery_app import celery_app
from sqlalchemy.orm import Session
from src.database.models.accounts import ActivationTokenModel
from src.database.session import SessionLocal


@celery_app.task(name="delete_expired_activation_tokens")
def delete_expired_activation_tokens() -> Union[str, None]:
    """Delete expired activation tokens"""
    print("TASK: Delete expired activation tokens")
    db: Session = SessionLocal()  # Open Session

    activation_tokens = db.query(ActivationTokenModel).all()
    count_expired_tokens = 0
    try:
        for activation_token in activation_tokens:
            if cast(datetime, activation_token.expires_at).replace(
                tzinfo=timezone.utc
            ) < datetime.now(timezone.utc):
                print(
                    f"Deleting expired activation token = {activation_token.token} (user_id = {activation_token.user_id})"
                )
                db.delete(activation_token)
                count_expired_tokens += 1
        db.commit()
    finally:
        db.close()  # Close Session

    if count_expired_tokens > 0:
        print(f"Successfully deleted {count_expired_tokens} expired activation tokens")
    else:
        print("There are no expired activation tokens at this moment.")
    return "Task completed!"
