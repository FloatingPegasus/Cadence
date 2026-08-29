if __package__:
    from .api_test_context import (
        ApiTestCase,
        CSRF_COOKIE_NAME,
        CSRF_HEADER_NAME,
        EmailDeliveryError,
        SESSION_COOKIE_NAME,
        SecretStr,
        TestClient,
        User,
        _create_token,
        _decode_token,
        app,
        asyncio,
        bcrypt,
        parse_qs,
        patch,
        settings,
        timedelta,
        urlparse,
    )
else:
    from api_test_context import (
        ApiTestCase,
        CSRF_COOKIE_NAME,
        CSRF_HEADER_NAME,
        EmailDeliveryError,
        SESSION_COOKIE_NAME,
        SecretStr,
        TestClient,
        User,
        _create_token,
        _decode_token,
        app,
        asyncio,
        bcrypt,
        parse_qs,
        patch,
        settings,
        timedelta,
        urlparse,
    )


class CadenceAuthApiTests(ApiTestCase):

    def test_dev_login_uses_only_environment_credentials(self) -> None:
        settings.dev_mode = True
        settings.dev_email = "dev@example.com"
        settings.dev_password = SecretStr("local-dev-password")
        settings.ai_api_key = ""

        wrong_password = self.client.post(
            "/api/auth/login",
            json={
                "username": "dev@example.com",
                "password": "wrong-password",
            },
        )
        login = self.client.post(
            "/api/auth/login",
            json={
                "username": "DEV@example.com",
                "password": "local-dev-password",
            },
        )
        me = self.client.get("/api/auth/me")
        response = self.client.get("/api/dev/ai/models")
        username_login = self.client.post(
            "/api/auth/login",
            json={
                "username": me.json()["username"],
                "password": "local-dev-password",
            },
        )
        bearer_without_dev_claim = self.client.get(
            "/api/auth/me",
            headers={
                "Authorization": (
                    f"Bearer {_create_token(login.json()['user_id'])}"
                )
            },
        )

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["is_developer"])
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "dev@example.com")
        self.assertTrue(me.json()["is_verified"])
        self.assertTrue(me.json()["is_developer"])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])
        self.assertEqual(username_login.status_code, 401)
        self.assertFalse(bearer_without_dev_claim.json()["is_developer"])

    def test_normal_login_accepts_username_or_email(self) -> None:
        async def add_ambiguous_username() -> None:
            async with self.session_factory() as db:
                password = bcrypt.hashpw(
                    b"different-password", bcrypt.gensalt()
                ).decode()
                db.add(
                    User(
                        username="alpha@example.com",
                        email="collision@example.com",
                        hashed_password=password,
                        is_verified=True,
                    )
                )
                await db.commit()

        asyncio.run(add_ambiguous_username())
        by_username = self.client.post(
            "/api/auth/login",
            json={"username": "alpha", "password": "test-password"},
        )
        by_email = self.client.post(
            "/api/auth/login",
            json={
                "username": "ALPHA@example.com",
                "password": "test-password",
            },
        )

        self.assertEqual(by_username.status_code, 200)
        self.assertEqual(by_email.status_code, 200)
        self.assertEqual(by_email.json()["user_id"], 1)

    def test_verification_token_cannot_authenticate_api_requests(self) -> None:
        verification_token = _create_token(
            1, purpose="verify_email", expires_delta=timedelta(hours=1)
        )

        response = self.client.get(
            "/api/habits",
            headers={"Authorization": f"Bearer {verification_token}"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid token")

    def test_unverified_account_is_blocked_until_emailed_token_is_used(
        self,
    ) -> None:
        settings.test_mode = False
        with patch(
            "cadence.app.web.routes.auth.send_verification_email"
        ) as send_email:
            registered = self.client.post(
                "/api/auth/register",
                json={
                    "username": "pending",
                    "email": "pending@example.com",
                    "password": "test-password",
                },
            )

        self.assertEqual(registered.status_code, 200)
        user_id = registered.json()["id"]
        verification_url = send_email.call_args.kwargs["verification_url"]
        verification_token = parse_qs(
            urlparse(verification_url).query
        )["token"][0]

        login_before = self.client.post(
            "/api/auth/login",
            json={"username": "pending", "password": "test-password"},
        )
        protected_before = self.client.get(
            "/api/habits",
            headers={
                "Authorization": f"Bearer {_create_token(user_id)}"
            },
        )
        verified = self.client.post(
            "/api/auth/verify",
            json={"token": verification_token},
        )
        habits_after_registration = self.client.get(
            "/api/habits",
            headers={"Authorization": f"Bearer {_create_token(user_id)}"},
        )
        login_after = self.client.post(
            "/api/auth/login",
            json={"username": "pending", "password": "test-password"},
        )

        self.assertEqual(login_before.status_code, 403)
        self.assertEqual(protected_before.status_code, 403)
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(habits_after_registration.status_code, 200)
        self.assertEqual(habits_after_registration.json(), [])
        self.assertEqual(login_after.status_code, 200)

    def test_unconfigured_mail_prints_a_verify_link_instead_of_failing(
        self,
    ) -> None:
        settings.test_mode = False
        settings.brevo_api_key = "replace-with-brevo-api-key"
        try:
            registered = self.client.post(
                "/api/auth/register",
                json={
                    "username": "nomaillocal",
                    "email": "nomaillocal@example.com",
                    "password": "test-password",
                },
            )
        finally:
            settings.test_mode = True
            settings.brevo_api_key = ""

        self.assertEqual(registered.status_code, 200)
        self.assertIn("server log", registered.json()["message"])

    def test_login_uses_secure_cookie_session_and_signed_csrf(self) -> None:
        settings.frontend_base_url = "https://app.example.test"
        client = TestClient(app, base_url="https://testserver")
        try:
            login = client.post(
                "/api/auth/login",
                json={"username": "alpha", "password": "test-password"},
            )
            self.assertEqual(login.status_code, 200)
            self.assertNotIn("access_token", login.json())

            cookie_headers = login.headers.get_list("set-cookie")
            session_header = next(
                header
                for header in cookie_headers
                if header.startswith(f"{SESSION_COOKIE_NAME}=")
            )
            csrf_header = next(
                header
                for header in cookie_headers
                if header.startswith(f"{CSRF_COOKIE_NAME}=")
            )
            for header in (session_header, csrf_header):
                self.assertIn("Max-Age=604800", header)
                self.assertIn("Path=/", header)
                self.assertIn("SameSite=lax", header)
                self.assertIn("Secure", header)
                self.assertNotIn("Domain=", header)
            self.assertIn("HttpOnly", session_header)
            self.assertNotIn("HttpOnly", csrf_header)

            session_token = client.cookies.get(SESSION_COOKIE_NAME)
            csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
            self.assertIsNotNone(session_token)
            self.assertIsNotNone(csrf_token)
            self.assertEqual(
                _decode_token(session_token, purpose="access")["csrf"],
                csrf_token,
            )
            self.assertNotIn(session_token, login.text)

            self.assertEqual(client.get("/api/auth/me").status_code, 200)
            missing_csrf = client.put(
                "/api/days/2026-07-24",
                json={"daily_note": "cookie session"},
            )
            self.assertEqual(missing_csrf.status_code, 403)
            mismatched_csrf = client.put(
                "/api/days/2026-07-24",
                headers={CSRF_HEADER_NAME: "wrong-token"},
                json={"daily_note": "cookie session"},
            )
            self.assertEqual(mismatched_csrf.status_code, 403)
            valid_csrf = client.put(
                "/api/days/2026-07-24",
                headers={CSRF_HEADER_NAME: csrf_token},
                json={"daily_note": "cookie session"},
            )
            self.assertEqual(valid_csrf.status_code, 200)

            logout = client.post(
                "/api/auth/logout",
                headers={CSRF_HEADER_NAME: csrf_token},
            )
            self.assertEqual(logout.status_code, 200)
            clear_headers = logout.headers.get_list("set-cookie")
            self.assertTrue(
                any(
                    header.startswith(f'{SESSION_COOKIE_NAME}="";')
                    and "Max-Age=0" in header
                    and "HttpOnly" in header
                    for header in clear_headers
                )
            )
            self.assertTrue(
                any(
                    header.startswith(f'{CSRF_COOKIE_NAME}="";')
                    and "Max-Age=0" in header
                    and "HttpOnly" not in header
                    for header in clear_headers
                )
            )
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
        finally:
            client.close()

    def _assert_deployment_cookie_security(
        self,
        frontend_base_url: str,
        request_base_url: str,
        secure: bool,
    ) -> None:
        settings.frontend_base_url = frontend_base_url
        client = TestClient(app, base_url=request_base_url)
        try:
            login = client.post(
                "/api/auth/login",
                json={"username": "alpha", "password": "test-password"},
            )
            self.assertEqual(login.status_code, 200)
            for header in login.headers.get_list("set-cookie"):
                self.assertEqual("; Secure" in header, secure)
        finally:
            client.close()

    def test_http_loopback_session_cookie_does_not_require_secure_transport(self) -> None:
        self._assert_deployment_cookie_security(
            "http://localhost:3001", "http://localhost", False
        )

    def test_cookie_security_follows_deployment_not_request_scheme(self) -> None:
        self._assert_deployment_cookie_security(
            "https://app.example.test", "http://testserver", True
        )
        self._assert_deployment_cookie_security(
            "http://localhost:3001", "https://testserver", False
        )

    def test_bearer_auth_remains_exempt_from_csrf_header(self) -> None:
        response = self.client.put(
            "/api/days/2026-07-24",
            headers=self.alpha_headers,
            json={"daily_note": "bearer compatibility"},
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_cookie_auth_is_cleared_without_detail_leak(self) -> None:
        client = TestClient(app, base_url="https://testserver")
        try:
            response = client.get(
                "/api/auth/me",
                headers={
                    "Cookie": (
                        f"{SESSION_COOKIE_NAME}=not-a-token; "
                        f"{CSRF_COOKIE_NAME}=stale-csrf"
                    )
                },
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Invalid token"})
            clear_headers = response.headers.get_list("set-cookie")
            self.assertEqual(len(clear_headers), 2)
            self.assertTrue(
                all("Max-Age=0" in header for header in clear_headers)
            )
        finally:
            client.close()

    def test_delivery_failure_is_visible_and_resend_recovers_account(
        self,
    ) -> None:
        settings.test_mode = False
        with patch(
            "cadence.app.web.routes.auth.send_verification_email",
            side_effect=EmailDeliveryError("provider rejected sender"),
        ):
            registered = self.client.post(
                "/api/auth/register",
                json={
                    "username": "resend",
                    "email": "resend@example.com",
                    "password": "test-password",
                },
            )

        with patch(
            "cadence.app.web.routes.auth.send_verification_email"
        ) as send_email:
            resent = self.client.post(
                "/api/auth/verification/resend",
                json={"email": "resend@example.com"},
            )

        self.assertEqual(registered.status_code, 503)
        self.assertIn(
            "verification email could not be sent",
            registered.json()["detail"],
        )
        self.assertEqual(resent.status_code, 200)
        send_email.assert_called_once()

    def test_resend_matches_legacy_mixed_case_email(self) -> None:
        async def add_legacy_user() -> None:
            async with self.session_factory() as db:
                db.add(
                    User(
                        username="legacy-email",
                        email="Legacy.Email@Example.com",
                        hashed_password=bcrypt.hashpw(
                            b"test-password", bcrypt.gensalt()
                        ).decode(),
                        is_verified=False,
                    )
                )
                await db.commit()

        asyncio.run(add_legacy_user())
        with patch(
            "cadence.app.web.routes.auth.send_verification_email"
        ) as send_email:
            response = self.client.post(
                "/api/auth/verification/resend",
                json={"email": "LEGACY.EMAIL@EXAMPLE.COM"},
            )

        self.assertEqual(response.status_code, 200)
        send_email.assert_called_once()
