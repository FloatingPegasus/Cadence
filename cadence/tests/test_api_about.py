if __package__:
    from .api_test_context import ApiTestCase
else:
    from api_test_context import ApiTestCase

DAY = "2026-07-24"


class CadenceAboutYouApiTests(ApiTestCase):
    def test_about_text_is_saved_trimmed_and_capped(self) -> None:
        saved = self.client.put(
            "/api/account/about",
            headers=self.alpha_headers,
            json={"about": "  Founder. Walks help when I spiral.  "},
        )
        too_long = self.client.put(
            "/api/account/about",
            headers=self.alpha_headers,
            json={"about": "x" * 1_501},
        )
        me = self.client.get("/api/auth/me", headers=self.alpha_headers).json()
        other = self.client.get("/api/auth/me", headers=self.beta_headers).json()
        exported = self.client.get(
            "/api/account/export", headers=self.alpha_headers
        ).json()

        self.assertEqual(saved.json(), {"about": "Founder. Walks help when I spiral."})
        self.assertEqual(too_long.status_code, 422)
        self.assertEqual(me["about"], "Founder. Walks help when I spiral.")
        self.assertEqual(other["about"], "")
        self.assertEqual(
            exported["account"]["about"], "Founder. Walks help when I spiral."
        )

    def test_goals_are_long_term_or_short_term(self) -> None:
        for kind, expected in (
            ("long_term", 201),
            ("short_term", 201),
            ("ultimate", 422),
            ("secondary", 422),
        ):
            response = self.client.post(
                "/api/goals",
                headers=self.alpha_headers,
                json={"kind": kind, "title": f"A {kind} goal"},
            )
            self.assertEqual(response.status_code, expected, kind)

    def test_preview_shows_the_exact_context_in_order(self) -> None:
        self.client.put(
            "/api/account/about",
            headers=self.alpha_headers,
            json={"about": "Founder of a small app."},
        )
        self.client.post(
            "/api/goals",
            headers=self.alpha_headers,
            json={"kind": "short_term", "title": "Ship About you"},
        )
        self.client.post(
            f"/api/days/{DAY}/logs",
            headers=self.alpha_headers,
            json={"content": "Wrote the migration", "hour": 9},
        )

        preview = self.client.get(
            f"/api/account/context?date={DAY}", headers=self.alpha_headers
        ).json()["text"]
        other = self.client.get(
            f"/api/account/context?date={DAY}", headers=self.beta_headers
        ).json()["text"]

        self.assertTrue(preview.startswith("About them:\nFounder of a small app."))
        self.assertLess(
            preview.index("Goals:\n- Short term: Ship About you"),
            preview.index("Habits:\n- Read: not yet"),
        )
        self.assertTrue(preview.endswith("Today:\nThey at 9 AM: Wrote the migration"))
        self.assertNotIn("Founder", other)
