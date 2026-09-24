if __package__:
    from .api_test_context import ApiTestCase, AsyncMock, patch, settings
else:
    from api_test_context import ApiTestCase, AsyncMock, patch, settings

SUMMARY_COMPLETION = (
    "cadence.app.domains.summaries.service.ai_service.chat_with_fallback"
)
REPLY_COMPLETION = (
    "cadence.app.domains.companion.service.ai_service.chat_with_fallback"
)


class CadenceMemoryApiTests(ApiTestCase):
    def note(self, date: str, text: str, headers=None) -> None:
        self.client.put(
            f"/api/days/{date}",
            headers=headers or self.alpha_headers,
            json={"daily_note": text},
        )

    def status(self, date: str) -> str:
        return self.client.get(
            f"/api/days/{date}", headers=self.alpha_headers
        ).json()["status"]

    def test_first_request_of_a_new_day_closes_older_days_with_content(self) -> None:
        self.note("2026-07-20", "Wrote the plan")
        self.client.get("/api/days/2026-07-21/logs", headers=self.alpha_headers)
        self.client.put(
            "/api/days/2026-07-21", headers=self.alpha_headers, json={"daily_note": ""}
        )
        self.note("2026-07-22", "Today so far")
        self.note("2026-07-19", "Beta's day", headers=self.beta_headers)

        first = self.client.post(
            "/api/days/2026-07-22/begin", headers=self.alpha_headers
        )
        again = self.client.post(
            "/api/days/2026-07-22/begin", headers=self.alpha_headers
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"closed": ["2026-07-20"]})
        self.assertEqual(again.json(), {"closed": []})
        self.assertEqual(self.status("2026-07-20"), "closed")
        self.assertEqual(self.status("2026-07-21"), "open")
        self.assertEqual(self.status("2026-07-22"), "open")
        beta_day = self.client.get(
            "/api/days/2026-07-19", headers=self.beta_headers
        ).json()
        self.assertEqual(beta_day["status"], "open")

    def test_days_stay_open_when_auto_close_is_off(self) -> None:
        self.note("2026-07-20", "Wrote the plan")
        updated = self.client.put(
            "/api/account/day-settings",
            headers=self.alpha_headers,
            json={"day_ends_at": 2, "auto_close": False},
        )
        me = self.client.get("/api/auth/me", headers=self.alpha_headers).json()
        begun = self.client.post(
            "/api/days/2026-07-22/begin", headers=self.alpha_headers
        )
        invalid = self.client.put(
            "/api/account/day-settings",
            headers=self.alpha_headers,
            json={"day_ends_at": 13, "auto_close": True},
        )

        self.assertEqual(updated.json(), {"day_ends_at": 2, "auto_close": False})
        self.assertEqual((me["day_ends_at"], me["auto_close"]), (2, False))
        self.assertEqual(begun.json(), {"closed": []})
        self.assertEqual(self.status("2026-07-20"), "open")
        self.assertEqual(invalid.status_code, 422)

    def test_new_accounts_default_to_a_4_am_boundary(self) -> None:
        beta = self.client.get("/api/auth/me", headers=self.beta_headers).json()
        self.assertEqual((beta["day_ends_at"], beta["auto_close"]), (4, True))

    def test_closing_writes_summaries_but_keeps_edited_ones(self) -> None:
        settings.ai_enabled = True
        self.note("2026-07-20", "Shipped the migration")
        self.note("2026-07-21", "Fixed the deploy")
        self.note("2026-07-01", "An old day")
        self.client.put(
            "/api/days/2026-07-21/summary",
            headers=self.alpha_headers,
            json={"content": "My own words about the deploy."},
        )

        with patch(SUMMARY_COMPLETION, new_callable=AsyncMock) as completion:
            completion.return_value = {
                "provider": "nvidia",
                "model": "z-ai/glm-5.2",
                "content": "A steady day that ended with the migration shipped.",
            }
            begun = self.client.post(
                "/api/days/2026-07-22/begin", headers=self.alpha_headers
            )

        self.assertEqual(
            begun.json()["closed"], ["2026-07-01", "2026-07-20", "2026-07-21"]
        )
        self.assertEqual(completion.await_count, 1)
        generated = self.client.get(
            "/api/days/2026-07-20/summary", headers=self.alpha_headers
        ).json()
        kept = self.client.get(
            "/api/days/2026-07-21/summary", headers=self.alpha_headers
        ).json()
        old = self.client.get(
            "/api/days/2026-07-01/summary", headers=self.alpha_headers
        ).json()
        self.assertEqual(
            generated["content"],
            "A steady day that ended with the migration shipped.",
        )
        self.assertEqual(kept["content"], "My own words about the deploy.")
        self.assertIsNone(old)

    def test_no_summaries_without_consent(self) -> None:
        settings.ai_enabled = True
        self.note("2026-07-20", "Beta's private day", headers=self.beta_headers)
        with patch(SUMMARY_COMPLETION, new_callable=AsyncMock) as completion:
            begun = self.client.post(
                "/api/days/2026-07-22/begin", headers=self.beta_headers
            )
        self.assertEqual(begun.json(), {"closed": ["2026-07-20"]})
        completion.assert_not_awaited()

    def test_memory_uses_the_edited_summary(self) -> None:
        settings.ai_enabled = True
        self.note("2026-07-21", "Rough day")
        self.client.put(
            "/api/days/2026-07-21/summary",
            headers=self.alpha_headers,
            json={"content": "Hard day, but I kept the streak."},
        )
        with patch(REPLY_COMPLETION, new_callable=AsyncMock) as completion:
            completion.return_value = {"content": "Keep going."}
            self.client.post(
                "/api/days/2026-07-22/logs",
                headers=self.alpha_headers,
                json={"content": "Starting again", "hour": 9, "reply": True},
            )

        context = completion.await_args.kwargs["messages"][1]["content"]
        self.assertIn(
            "Recent days:\n- Tue Jul 21: Hard day, but I kept the streak.", context
        )
