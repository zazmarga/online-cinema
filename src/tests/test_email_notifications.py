import re

import httpx
from bs4 import BeautifulSoup

from src.tests.conftest import test_settings
from src.tests.test_accounts import (
    test_register_user_success,
    test_activate_account_success,
    test_request_password_reset_token_success,
    test_reset_password_success,
    test_restore_activation_success,
)
from src.tests.test_movies import (
    test_user_can_put_likes_to_comments,
    test_user_can_reply_for_comments,
)

MAILHOG_URL = f"http://{test_settings.EMAIL_HOST}:{test_settings.MAILHOG_API_PORT}/api/v2/messages"


def test_registered_user_email_notification(
    client, db_session, seed_user_groups, cleanup_mailhog
):
    """
    Test that a registered user email notification is sent.
    """
    # call  with  payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    test_register_user_success(client, db_session, seed_user_groups)
    user_email = "testuser@example.com"

    with httpx.Client() as email_client:
        mailhog_response = email_client.get(MAILHOG_URL)

    assert mailhog_response.status_code == 200, "Failed to fetch emails from MailHog!"
    messages = mailhog_response.json()["items"]
    assert len(messages) > 0, "No emails were sent!"
    print(f"Email notification sent to {len(messages)} emails")

    email = messages[0]
    assert (
        email["Content"]["Headers"]["To"][0] == user_email
    ), "Recipient email does not match!"
    email_subject = email["Content"]["Headers"].get("Subject", [None])[0]
    assert (
        email_subject == "Account Activation"
    ), f"Expected subject 'Account Activation', but got '{email_subject}'"

    email_html = email["Content"]["Body"]
    soup = BeautifulSoup(email_html, "html.parser")

    email_element = soup.find("strong", id="email")
    assert email_element is not None, "Email element with id 'email' not found!"

    assert (
        email_element.text == user_email
    ), "Email content does not match the user's email!"

    link_element = soup.find("a", id="link")
    assert link_element is not None, "Login link element not found!"


def test_account_activation_email_notification(
    client, db_session, seed_user_groups, cleanup_mailhog
):
    """
    Test that an account activation successfully email notification is sent.
    """
    # call  with  payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    test_activate_account_success(client, db_session, seed_user_groups)
    user_email = "testuser@example.com"

    with httpx.Client() as email_client:
        mailhog_response = email_client.get(MAILHOG_URL)

    assert mailhog_response.status_code == 200, "Failed to fetch emails from MailHog!"
    messages = mailhog_response.json()["items"]
    assert len(messages) > 0, "No emails were sent!"
    print(f"Email notification sent to {len(messages)} emails")

    email = messages[0]
    assert (
        email["Content"]["Headers"]["To"][0] == user_email
    ), "Recipient email does not match!"
    email_subject = email["Content"]["Headers"].get("Subject", [None])[0]
    assert (
        email_subject == "Account Activated Successfully"
    ), f"Expected subject 'Account Activated Successfully', but got '{email_subject}'"

    email_html = email["Content"]["Body"]
    soup = BeautifulSoup(email_html, "html.parser")

    email_element = soup.find("strong", id="email")
    assert email_element is not None, "Email element with id 'email' not found!"

    assert (
        email_element.text == user_email
    ), "Email content does not match the user's email!"

    link_element = soup.find("a", id="link")
    assert link_element is not None, "Login link element not found!"


def test_request_password_reset_email_notification(
    client, db_session, seed_user_groups, cleanup_mailhog
):
    """
    Test that a request password reset email notification is sent.
    """
    test_request_password_reset_token_success(client, db_session, seed_user_groups)
    # call  with  payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    user_email = "testuser@example.com"

    with httpx.Client() as email_client:
        mailhog_response = email_client.get(MAILHOG_URL)

    assert mailhog_response.status_code == 200, "Failed to fetch emails from MailHog!"
    messages = mailhog_response.json()["items"]
    assert len(messages) > 0, "No emails were sent!"
    print(f"Email notification sent to {len(messages)} emails")

    email = messages[0]
    assert (
        email["Content"]["Headers"]["To"][0] == user_email
    ), "Recipient email does not match!"
    email_subject = email["Content"]["Headers"].get("Subject", [None])[0]
    assert (
        email_subject == "Password Reset Request"
    ), f"Expected subject 'Password Reset Request', but got '{email_subject}'"

    email_html = email["Content"]["Body"]
    soup = BeautifulSoup(email_html, "html.parser")

    email_element = soup.find("strong", id="email")
    assert email_element is not None, "Email element with id 'email' not found!"

    assert (
        email_element.text == user_email
    ), "Email content does not match the user's email!"

    link_element = soup.find("a", id="link")
    assert link_element is not None, "Login link element not found!"


def test_password_reset_successfully_email_notification(
    client, db_session, seed_user_groups, cleanup_mailhog
):
    """
    Test the complete password reset email notification is sent.
    """
    test_reset_password_success(client, db_session, seed_user_groups)
    # call  with  payload = {"email": "testuser@example.com", "password": "OldPassword123!"}
    user_email = "testuser@example.com"

    with httpx.Client() as email_client:
        mailhog_response = email_client.get(MAILHOG_URL)

    assert mailhog_response.status_code == 200, "Failed to fetch emails from MailHog!"
    messages = mailhog_response.json()["items"]
    assert len(messages) > 0, "No emails were sent!"
    print(f"Email notification sent to {len(messages)} emails")

    email = messages[0]
    assert (
        email["Content"]["Headers"]["To"][0] == user_email
    ), "Recipient email does not match!"
    email_subject = email["Content"]["Headers"].get("Subject", [None])[0]
    assert (
        email_subject == "Your Password Has Been Successfully Reset"
    ), f"Expected subject 'Your Password Has Been Successfully Reset', but got '{email_subject}'"

    email_html = email["Content"]["Body"]
    soup = BeautifulSoup(email_html, "html.parser")

    email_element = soup.find("strong", id="email")
    assert email_element is not None, "Email element with id 'email' not found!"

    assert (
        email_element.text == user_email
    ), "Email content does not match the user's email!"

    link_element = soup.find("a", id="link")
    assert link_element is not None, "Login link element not found!"


def test_restore_activation_email_notification(
    client, db_session, seed_user_groups, cleanup_mailhog
):
    """
    Test the restore activation email notification is sent.
    """
    test_restore_activation_success(client, db_session, seed_user_groups)
    # call  with  payload = {"email": "testuser@example.com"}
    user_email = "testuser@example.com"

    with httpx.Client() as email_client:
        mailhog_response = email_client.get(MAILHOG_URL)

    assert mailhog_response.status_code == 200, "Failed to fetch emails from MailHog!"
    messages = mailhog_response.json()["items"]
    assert len(messages) > 0, "No emails were sent!"
    print(f"Email notification sent to {len(messages)} emails")

    email = messages[0]
    assert (
        email["Content"]["Headers"]["To"][0] == user_email
    ), "Recipient email does not match!"
    email_subject = email["Content"]["Headers"].get("Subject", [None])[0]
    assert (
        email_subject == "Restore Activation"
    ), f"Expected subject 'Restore Activation', but got '{email_subject}'"

    email_html = email["Content"]["Body"]
    soup = BeautifulSoup(email_html, "html.parser")

    email_element = soup.find("strong", id="email")
    assert email_element is not None, "Email element with id 'email' not found!"

    assert (
        email_element.text == user_email
    ), "Email content does not match the user's email!"

    link_element = soup.find("a", id="link")
    assert link_element is not None, "Login link element not found!"


def test_about_like_to_user_comment_email_notification(
    client, db_session, jwt_manager, seed_database, cleanup_mailhog
):
    """
    Test about like to user comment email notification is sent.
    """
    test_user_can_put_likes_to_comments(client, db_session, jwt_manager, seed_database)
    # call  with   email="other_test@mate.com"
    user_email = "other_test@mate.com"

    with httpx.Client() as email_client:
        mailhog_response = email_client.get(MAILHOG_URL)

    assert mailhog_response.status_code == 200, "Failed to fetch emails from MailHog!"
    messages = mailhog_response.json()["items"]
    assert len(messages) > 0, "No emails were sent!"
    print(f"Email notification sent to {len(messages)} emails")

    email = messages[0]
    assert (
        email["Content"]["Headers"]["To"][0] == user_email
    ), "Recipient email does not match!"
    email_subject = email["Content"]["Headers"].get("Subject", [None])[0]
    assert (
        email_subject == "Your comment has been liked or replied"
    ), f"Expected subject 'Your comment has been liked or replied', but got '{email_subject}'"

    email_html = email["Content"]["Body"]
    soup = BeautifulSoup(email_html, "html.parser")

    match_comment_id = re.search(r"comment_id=(\d+)", email_html)
    assert match_comment_id is not None, "Email element with id 'comment_id' not found!"

    match_movie_id = re.search(r"movie_id=(\d+)", email_html)
    assert match_movie_id is not None, "Email element with id 'movie_id' not found!"

    link_element = soup.find("a", id="link")
    assert link_element is not None, "Login link element not found!"


def test_about_reply_to_user_comment_email_notification(
    client, db_session, jwt_manager, seed_database, cleanup_mailhog
):
    """
    Test about any reply to user comment email notification is sent.
    """
    test_user_can_reply_for_comments(client, db_session, jwt_manager, seed_database)
    # call  with   email="other_test@mate.com"
    user_email = "other_test@mate.com"

    with httpx.Client() as email_client:
        mailhog_response = email_client.get(MAILHOG_URL)

    assert mailhog_response.status_code == 200, "Failed to fetch emails from MailHog!"
    messages = mailhog_response.json()["items"]
    assert len(messages) > 0, "No emails were sent!"
    print(f"Email notification sent to {len(messages)} emails")

    email = messages[0]
    assert (
        email["Content"]["Headers"]["To"][0] == user_email
    ), "Recipient email does not match!"
    email_subject = email["Content"]["Headers"].get("Subject", [None])[0]
    assert (
        email_subject == "Your comment has been liked or replied"
    ), f"Expected subject 'Your comment has been liked or replied', but got '{email_subject}'"

    email_html = email["Content"]["Body"]
    soup = BeautifulSoup(email_html, "html.parser")

    match_comment_id = re.search(r"comment_id=(\d+)", email_html)
    assert match_comment_id is not None, "Email element with id 'comment_id' not found!"

    match_movie_id = re.search(r"movie_id=(\d+)", email_html)
    assert match_movie_id is not None, "Email element with id 'movie_id' not found!"

    link_element = soup.find("a", id="link")
    assert link_element is not None, "Login link element not found!"
