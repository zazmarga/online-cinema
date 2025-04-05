from abc import ABC, abstractmethod


class EmailSenderInterface(ABC):

    @abstractmethod
    def send_activation_email(self, email: str, activation_link: str) -> None:
        pass

    @abstractmethod
    def send_activation_complete_email(self, email: str, login_link: str) -> None:
        pass

    @abstractmethod
    def send_activation_restore_email(self, email: str, activation_link: str) -> None:
        pass

    @abstractmethod
    def send_password_reset_email(self, email: str, reset_link: str) -> None:
        pass

    @abstractmethod
    def send_password_reset_complete_email(self, email: str, login_link: str) -> None:
        pass

    @abstractmethod
    def send_like_reply_notification_email(
        self, email: str, comment_link: str, message: str
    ) -> None:
        pass

    @abstractmethod
    def send_payment_confirmation_email(
        self, email: str, payments_link: str, message: str
    ) -> None:
        pass
