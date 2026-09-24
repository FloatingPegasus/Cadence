import json

if __package__:
    from .api_test_context import ApiTestCase
else:
    from api_test_context import ApiTestCase


class CadenceLogsAndGoalsApiTests(ApiTestCase):
    def test_logs_are_one_user_scoped_stream_with_optional_hours(self) -> None:
        timed = self.client.post(
            "/api/days/2026-07-24/logs",
            headers=self.alpha_headers,
            json={"hour": 9, "content": "  Deep work  "},
        )
        loose = self.client.post(
            "/api/days/2026-07-24/logs",
            headers=self.alpha_headers,
            json={"content": "Felt scattered after lunch"},
        )
        listed = self.client.get(
            "/api/days/2026-07-24/logs",
            headers=self.alpha_headers,
        )
        other = self.client.get(
            "/api/days/2026-07-24/logs",
            headers=self.beta_headers,
        )

        self.assertEqual(timed.status_code, 201)
        self.assertEqual(timed.json()["log"]["content"], "Deep work")
        self.assertEqual(timed.json()["log"]["hour"], 9)
        self.assertEqual(timed.json()["log"]["role"], "user")
        self.assertIsNone(loose.json()["log"]["hour"])
        self.assertEqual(
            [(entry["hour"], entry["content"]) for entry in listed.json()],
            [(9, "Deep work"), (None, "Felt scattered after lunch")],
        )
        self.assertEqual(other.json(), [])

    def test_logs_edit_and_delete_only_for_their_owner(self) -> None:
        entry_id = self.client.post(
            "/api/days/2026-07-24/logs",
            headers=self.alpha_headers,
            json={"hour": 14, "content": "Draft"},
        ).json()["log"]["id"]

        stolen = self.client.patch(
            f"/api/days/2026-07-24/logs/{entry_id}",
            headers=self.beta_headers,
            json={"content": "Hijack"},
        )
        wrong_day = self.client.patch(
            f"/api/days/2026-07-25/logs/{entry_id}",
            headers=self.alpha_headers,
            json={"content": "Elsewhere"},
        )
        edited = self.client.patch(
            f"/api/days/2026-07-24/logs/{entry_id}",
            headers=self.alpha_headers,
            json={"content": "  Wrote the outline  "},
        )
        blank = self.client.patch(
            f"/api/days/2026-07-24/logs/{entry_id}",
            headers=self.alpha_headers,
            json={"content": "   "},
        )
        not_theirs = self.client.delete(
            f"/api/days/2026-07-24/logs/{entry_id}",
            headers=self.beta_headers,
        )

        self.assertEqual(stolen.status_code, 404)
        self.assertEqual(wrong_day.status_code, 404)
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["content"], "Wrote the outline")
        self.assertEqual(edited.json()["hour"], 14)
        self.assertEqual(blank.status_code, 422)
        self.assertEqual(not_theirs.status_code, 404)

        deleted = self.client.delete(
            f"/api/days/2026-07-24/logs/{entry_id}",
            headers=self.alpha_headers,
        )
        again = self.client.delete(
            f"/api/days/2026-07-24/logs/{entry_id}",
            headers=self.alpha_headers,
        )
        listed = self.client.get(
            "/api/days/2026-07-24/logs",
            headers=self.alpha_headers,
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(again.status_code, 404)
        self.assertEqual(listed.json(), [])

    def test_logs_reject_out_of_range_hours_and_blank_content(self) -> None:
        late = self.client.post(
            "/api/days/2026-07-24/logs",
            headers=self.alpha_headers,
            json={"hour": 24, "content": "Too late"},
        )
        blank = self.client.post(
            "/api/days/2026-07-24/logs",
            headers=self.alpha_headers,
            json={"hour": 9, "content": "   "},
        )
        self.assertEqual(late.status_code, 422)
        self.assertEqual(blank.status_code, 422)

    def test_summary_sources_keep_hours_apart_from_the_thread(self) -> None:
        for body in (
            {"hour": 15, "content": "Reviewed the draft"},
            {"hour": 9, "content": "Deep work"},
            {"content": "Needed a walk"},
        ):
            self.client.post(
                "/api/days/2026-07-24/logs",
                headers=self.alpha_headers,
                json=body,
            )
        self.client.put(
            "/api/days/2026-07-24/summary",
            headers=self.alpha_headers,
            json={"content": "A focused morning."},
        )
        exported = self.client.get(
            "/api/account/export",
            headers=self.alpha_headers,
        ).json()
        snapshot = json.loads(
            exported["resources"]["summary_artifacts"][0]["source_snapshot"]
        )

        self.assertEqual(
            snapshot["hours"],
            [
                {"hour": 9, "content": "Deep work"},
                {"hour": 15, "content": "Reviewed the draft"},
            ],
        )
        self.assertEqual(
            snapshot["conversation"],
            [{"role": "user", "content": "Needed a walk"}],
        )

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
