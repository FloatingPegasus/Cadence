from __future__ import annotations

from html import escape
import logging
from urllib.parse import urlsplit

from ..config import settings

logger = logging.getLogger("cadence.email")


class EmailDeliveryError(RuntimeError):
    pass


def send_verification_email(to_email: str, to_name: str, verification_url: str) -> None:
    """Send the email-verification message.

    Automated tests can suppress delivery with TEST_MODE. Normal local
    development uses the configured Brevo account.
    """
    subject = "Verify your Cadence account"
    html = _verification_html(to_name, verification_url)
    text = f"Hi {to_name},\n\nVerify your Cadence account by visiting:\n{verification_url}\n\nIf you didn't create an account, you can ignore this email.\n"

    if settings.test_mode or not settings.mail_is_configured:
        logger.warning(
            "Verification email not sent. Recipient=%s\nVerification URL: %s",
            to_email,
            verification_url,
        )
        print(f"\nVerify {to_email} -> {verification_url}\n")
        return

    try:
        _send_via_brevo(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html_content=html,
            text_content=text,
        )
    except EmailDeliveryError:
        raise
    except Exception as error:
        logger.exception("Brevo verification delivery failed")
        raise EmailDeliveryError(
            "Verification email delivery failed"
        ) from error


def _send_via_brevo(
    *,
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
    text_content: str,
) -> None:
    from brevo import (
        Brevo,
        SendTransacEmailRequestSender,
        SendTransacEmailRequestToItem,
    )

    if not settings.brevo_api_key:
        raise EmailDeliveryError(
            "CADENCE_BREVO_API_KEY is not configured"
        )

    client = Brevo(api_key=settings.brevo_api_key)
    sender = SendTransacEmailRequestSender(
        name=settings.from_name, email=settings.from_email
    )
    recipient = SendTransacEmailRequestToItem(email=to_email, name=to_name)
    client.transactional_emails.send_transac_email(
        sender=sender,
        to=[recipient],
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )
    logger.info("Verification email sent to %s", to_email)


def _verification_html(name: str, url: str) -> str:
    parsed_url = urlsplit(url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.username is not None
        or parsed_url.password is not None
        or any(char.isspace() for char in url)
    ):
        raise ValueError("Verification URL is not safe")
    safe_name = escape(name.replace("\r", " ").replace("\n", " "))
    safe_url = escape(url, quote=True)
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
      <h1 style="font-size: 20px; font-weight: 600; color: #1f2937; margin-bottom: 8px;">Cadence</h1>
      <p style="color: #6b7280; font-size: 14px; margin-bottom: 24px;">Daily continuity</p>
      <p style="font-size: 15px; color: #374151; margin-bottom: 16px;">Hi {safe_name},</p>
      <p style="font-size: 15px; color: #374151; margin-bottom: 24px;">
        Verify your account by clicking the button below. This link expires in
        {settings.verification_token_expire_hours} hours.
      </p>
      <p>
        <a href="{safe_url}"
           style="display: inline-block; padding: 10px 20px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500;">
          Verify email
        </a>
      </p>
      <p style="font-size: 13px; color: #9ca3af; margin-top: 32px;">
        If you didn't create a Cadence account, you can safely ignore this email.
      </p>
    </div>
    """
