"""Replaceable identity delivery port and explicit local-demo inbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from email.message import EmailMessage
from email.utils import formataddr
import smtplib
import ssl

from BE.app.core.config import Settings


@dataclass(frozen=True)
class DevelopmentDelivery:
    email: str
    purpose: str
    token: str
    expires_at: datetime


class DevelopmentOutbox:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], DevelopmentDelivery] = {}
        self._lock = RLock()

    def deliver(self, email: str, purpose: str, token: str, expires_at: datetime) -> None:
        with self._lock:
            self._items[(email, purpose)] = DevelopmentDelivery(
                email=email, purpose=purpose, token=token, expires_at=expires_at
            )

    def latest(self, email: str, purpose: str, now: datetime) -> DevelopmentDelivery | None:
        with self._lock:
            item = self._items.get((email, purpose))
            return item if item and item.expires_at > now else None

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


development_outbox = DevelopmentOutbox()


def send_identity_email(settings: Settings, email: str, purpose: str,
                        token: str, expires_at: datetime) -> str:
    """Return sent only after SMTP accepts mail; never log provider exceptions.

    This adapter deliberately does not retry sends: a timeout can happen after
    acceptance. Users can request a fresh single-use action through resend.
    """
    if settings.identity_dev_outbox_enabled:
        development_outbox.deliver(email, purpose, token, expires_at)
        return "sent"
    if not settings.smtp_configured:
        return "failed"
    subjects = {
        "verify_email": "Xác thực email Davel Trace",
        "recover_password": "Đặt lại mật khẩu Davel Trace",
        "cancel_deletion": "Khôi phục tài khoản Davel Trace",
    }
    try:
        message = EmailMessage()
        message["Subject"] = subjects[purpose]
        message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
        message["To"] = email
        message.set_content(
            f"{subjects[purpose]}\n\n"
            f"Nhập mã sau trong màn hình tương ứng của Davel Trace:\n\n{token}\n\n"
            f"Mã chỉ dùng một lần, hết hạn lúc {expires_at.isoformat()} (UTC).\n"
            "Nếu bạn không yêu cầu thao tác này, hãy bỏ qua email và không chia sẻ mã.\n"
        )
        context = ssl.create_default_context()
        factory = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
        kwargs = {"timeout": settings.smtp_timeout_seconds}
        if settings.smtp_ssl:
            kwargs["context"] = context
        with factory(settings.smtp_host, settings.smtp_port, **kwargs) as client:
            if settings.smtp_starttls:
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            password = settings.smtp_password
            if settings.smtp_host == "smtp.gmail.com":
                password = password.replace(" ", "")
            client.login(settings.smtp_username, password)
            refused = client.send_message(message)
            if refused:
                return "failed"
        return "sent"
    except (OSError, smtplib.SMTPException, ValueError, KeyError):
        return "failed"
