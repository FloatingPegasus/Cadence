if __package__:
    from .api_test_context import ApiTestCase
else:
    from api_test_context import ApiTestCase


class CadenceHoursAndGoalsApiTests(ApiTestCase):
    def test_hour_log_is_user_scoped_and_clears_on_empty(self) -> None:
        saved = self.client.put(
            "/api/days/2026-07-24/hours",
            headers=self.alpha_headers,
            json={"hour": 9, "content": "  Deep work  "},
        )
        listed = self.client.get(
            "/api/days/2026-07-24/hours",
            headers=self.alpha_headers,
        )
        other = self.client.get(
            "/api/days/2026-07-24/hours",
            headers=self.beta_headers,
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json(), {"hour": 9, "content": "Deep work"})
        self.assertEqual(listed.status_code, 200)
        slots = listed.json()
        self.assertEqual(len(slots), 24)
        self.assertEqual(slots[9], {"hour": 9, "content": "Deep work"})
        self.assertEqual(slots[8], {"hour": 8, "content": ""})
        self.assertEqual(other.json()[9]["content"], "")

        cleared = self.client.put(
            "/api/days/2026-07-24/hours",
            headers=self.alpha_headers,
            json={"hour": 9, "content": "   "},
        )
        self.assertEqual(cleared.json()["content"], "")
        refreshed = self.client.get(
            "/api/days/2026-07-24/hours",
            headers=self.alpha_headers,
        )
        self.assertEqual(refreshed.json()[9]["content"], "")

    def test_hour_log_rejects_out_of_range_hours(self) -> None:
        response = self.client.put(
            "/api/days/2026-07-24/hours",
            headers=self.alpha_headers,
            json={"hour": 24, "content": "Too late"},
        )
        self.assertEqual(response.status_code, 422)

    def test_goals_are_user_scoped_and_kind_checked(self) -> None:
        created = self.client.post(
            "/api/goals",
            headers=self.alpha_headers,
            json={
                "kind": "ultimate",
                "title": "Write every day",
                "notes": "A page is enough",
            },
        )
        listed = self.client.get("/api/goals", headers=self.alpha_headers)
        other = self.client.get("/api/goals", headers=self.beta_headers)
        invalid = self.client.post(
            "/api/goals",
            headers=self.alpha_headers,
            json={"kind": " vibes ", "title": "Nope"},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["kind"], "ultimate")
        self.assertEqual(listed.json()[0]["title"], "Write every day")
        self.assertEqual(other.json(), [])
        self.assertEqual(invalid.status_code, 422)

        goal_id = created.json()["id"]
        updated = self.client.patch(
            f"/api/goals/{goal_id}",
            headers=self.alpha_headers,
            json={"title": "Write most days"},
        )
        stolen = self.client.patch(
            f"/api/goals/{goal_id}",
            headers=self.beta_headers,
            json={"title": "Hijack"},
        )
        deleted = self.client.delete(
            f"/api/goals/{goal_id}",
            headers=self.alpha_headers,
        )
        missing = self.client.get("/api/goals", headers=self.alpha_headers)

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["title"], "Write most days")
        self.assertEqual(stolen.status_code, 404)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(missing.json(), [])
