import unittest
from unittest.mock import patch

if __package__:
    from .bootstrap import configure_test_environment
else:
    from bootstrap import configure_test_environment

configure_test_environment()

from cadence.app.config import settings
from cadence.app.services.email import send_verification_email


class EmailDeliveryTests(unittest.TestCase):
    def test_unconfigured_mail_logs_instead_of_calling_brevo(self) -> None:
        settings.test_mode = False
        settings.brevo_api_key = ""
        try:
            with patch("cadence.app.services.email._send_via_brevo") as send:
                send_verification_email(
                    "local@example.com",
                    "local",
                    "http://localhost:8000/verify?token=abc",
                )
        finally:
            settings.test_mode = True
            settings.brevo_api_key = ""
        send.assert_not_called()
