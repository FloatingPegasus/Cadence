import unittest
from datetime import datetime, timedelta, timezone

if __package__:
    from .bootstrap import configure_test_environment
else:
    from bootstrap import configure_test_environment

configure_test_environment()

from fastapi.testclient import TestClient
import jwt
from pydantic import ValidationError

from cadence.app import app
from cadence.app.config import Settings, settings
from cadence.app.services.email import _verification_html
from cadence.app.services.rate_limit import InMemoryRateLimiter, auth_rate_limiter
from cadence.app.web.routes.auth import (
    LoginBody,
    RegisterBody,
    _create_token,
    _decode_token,
)


class SecurityRegressionTests(unittest.TestCase):
    def test_dev_credentials_are_required_only_when_dev_mode_is_enabled(self) -> None:
        disabled = Settings(
            secret_key="a" * 40,
            test_mode=False,
            dev_mode=False,
            dev_email="",
            dev_password="",
            _env_file=None,
        )
        self.assertFalse(disabled.dev_mode)

        configured = Settings(
            secret_key="a" * 40,
            test_mode=False,
            dev_mode=True,
            dev_email="DEV@example.com",
            dev_password="local-dev-password",
            _env_file=None,
        )
        self.assertEqual(configured.dev_email, "dev@example.com")

        for invalid_values in (
            {"dev_email": "", "dev_password": "local-dev-password"},
            {"dev_email": "not-an-email", "dev_password": "local-dev-password"},
            {"dev_email": "dev@example.com", "dev_password": "short"},
        ):
            with self.subTest(invalid_values=invalid_values):
                with self.assertRaises(ValueError):
                    Settings(
                        secret_key="a" * 40,
                        test_mode=False,
                        dev_mode=True,
                        _env_file=None,
                        **invalid_values,
                    )

        leaked_password = "should-never-appear-in-errors"
        with self.assertRaises(ValidationError) as raised:
            Settings(
                secret_key="a" * 40,
                test_mode=False,
                dev_mode=True,
                dev_email="not-an-email",
                dev_password=leaked_password,
                _env_file=None,
            )
        self.assertNotIn(leaked_password, str(raised.exception))

    def test_production_signing_configuration_rejects_defaults_and_algorithms(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                secret_key="change-me-in-production",
                test_mode=False,
                _env_file=None,
            )

    def test_public_verification_base_urls_require_https(self) -> None:
        with self.assertRaises(ValueError):
            Settings(
                secret_key="a" * 40,
                test_mode=False,
                frontend_base_url="http://example.com",
                cors_origins="https://example.com",
                _env_file=None,
            )
        local = Settings(
            secret_key="a" * 40,
            test_mode=False,
            frontend_base_url="http://localhost:3001",
            cors_origins="http://localhost:3001",
            _env_file=None,
        )
        self.assertEqual(local.frontend_base_url, "http://localhost:3001")
        with self.assertRaises(ValueError):
            Settings(
                secret_key="a" * 40,
                algorithm="HS512",
                test_mode=False,
                _env_file=None,
            )

    def test_verification_email_escapes_name_and_url(self) -> None:
        rendered = _verification_html(
            '<script>alert("x")</script>',
            "https://example.test/verify?token=abc&next=1",
        )
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("token=abc&amp;next=1", rendered)
        with self.assertRaises(ValueError):
            _verification_html("Cadence", "javascript:alert(1)")

    def test_auth_names_are_bounded_after_normalization(self) -> None:
        body = RegisterBody(
            username="  abc  ",
            email="alpha@example.com",
            password="test-password",
        )
        self.assertEqual(body.username, "abc")
        with self.assertRaises(ValueError):
            RegisterBody(
                username="  a  ",
                email="short@example.com",
                password="test-password",
            )
        with self.assertRaises(ValueError):
            LoginBody(username="   ", password="test-password")

    def test_verification_endpoint_enforces_rate_limit(self) -> None:
        original_test_mode = settings.test_mode
        settings.test_mode = False
        auth_rate_limiter.clear()
        try:
            with TestClient(app) as client:
                for _ in range(settings.auth_verification_rate_limit):
                    response = client.post(
                        "/api/auth/verify",
                        json={"token": "not-a-token"},
                    )
                    self.assertEqual(response.status_code, 400)
                blocked = client.post(
                    "/api/auth/verify",
                    json={"token": "not-a-token"},
                )
            self.assertEqual(blocked.status_code, 429)
            self.assertGreater(int(blocked.headers["Retry-After"]), 0)
        finally:
            settings.test_mode = original_test_mode
            auth_rate_limiter.clear()

    def test_tokens_require_expected_purpose_and_algorithm(self) -> None:
        token = _create_token(1)
        self.assertEqual(_decode_token(token, purpose="access")["sub"], "1")
        with self.assertRaises(jwt.PyJWTError):
            _decode_token(token, purpose="verify_email")

        claims = {
            "sub": "1",
            "purpose": "access",
            "iss": "cadence",
            "jti": "test-jti",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        non_hs256 = jwt.encode(claims, "a" * 64, algorithm="HS512")
        with self.assertRaises(jwt.PyJWTError):
            _decode_token(non_hs256, purpose="access")

    def test_security_headers_are_present(self) -> None:
        with TestClient(app) as client:
            response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(
            response.headers["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )

    def test_cors_allows_explicit_credentials_and_csrf_header(self) -> None:
        with TestClient(app) as client:
            response = client.options(
                "/api/auth/me",
                headers={
                    "Origin": "http://localhost:3001",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "X-CSRF-Token",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:3001",
        )
        self.assertEqual(
            response.headers["access-control-allow-credentials"], "true"
        )
        self.assertIn(
            "X-CSRF-Token",
            response.headers["access-control-allow-headers"],
        )

    def test_rate_limiter_blocks_only_after_limit(self) -> None:
        limiter = InMemoryRateLimiter()
        self.assertIsNone(
            limiter.retry_after("test", limit=2, window_seconds=60)
        )
        self.assertIsNone(
            limiter.retry_after("test", limit=2, window_seconds=60)
        )
        self.assertGreater(
            limiter.retry_after("test", limit=2, window_seconds=60) or 0,
            0,
        )
        limiter.clear()
        self.assertIsNone(
            limiter.retry_after("test", limit=2, window_seconds=60)
        )


if __name__ == "__main__":
    unittest.main()
