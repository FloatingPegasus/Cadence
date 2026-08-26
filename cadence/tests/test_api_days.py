if __package__:
    from .api_test_context import ApiTestCase, ThreadPoolExecutor
else:
    from api_test_context import ApiTestCase, ThreadPoolExecutor


class CadenceDaysApiTests(ApiTestCase):

    def test_two_users_can_own_the_same_calendar_day(self) -> None:
        alpha = self.client.put(
            "/api/days/2026-07-23",
            headers=self.alpha_headers,
            json={"daily_note": "Alpha context"},
        )
        beta = self.client.put(
            "/api/days/2026-07-23",
            headers=self.beta_headers,
            json={"daily_note": "Beta context"},
        )

        self.assertEqual(alpha.status_code, 200)
        self.assertEqual(beta.status_code, 200)
        self.assertNotEqual(alpha.json()["id"], beta.json()["id"])
        self.assertEqual(alpha.json()["daily_note"], "Alpha context")
        self.assertEqual(beta.json()["daily_note"], "Beta context")

    def test_day_can_close_and_reopen_without_compliance_requirements(self) -> None:
        closed = self.client.patch(
            "/api/days/2026-07-23/status",
            headers=self.alpha_headers,
            json={"status": "closed"},
        )
        reopened = self.client.patch(
            "/api/days/2026-07-23/status",
            headers=self.alpha_headers,
            json={"status": "open"},
        )

        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "closed")
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.json()["status"], "open")

    def test_log_entry_times_are_explicit_utc(self) -> None:
        created = self.client.post(
            "/api/days/2026-07-23/conversation",
            headers=self.alpha_headers,
            json={"content": "Checked the local time display"},
        )
        listed = self.client.get(
            "/api/days/2026-07-23/conversation",
            headers=self.alpha_headers,
        )

        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["created_at"].endswith("Z"))
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(listed.json()[0]["created_at"].endswith("Z"))

    def test_closure_preview_is_bounded_informational_and_user_scoped(
        self,
    ) -> None:
        self.client.put(
            "/api/days/2026-07-23",
            headers=self.alpha_headers,
            json={"daily_note": "The closure flow became coherent."},
        )
        self.client.put(
            "/api/days/2026-07-23/checkin",
            headers=self.alpha_headers,
            json={"energy_level": 3, "notes": "A steady day"},
        )
        for content in ("First raw trace", "Second raw trace"):
            self.client.post(
                "/api/days/2026-07-23/conversation",
                headers=self.alpha_headers,
                json={"content": content},
            )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={
                "habit_id": 1,
                "date": "2026-07-23",
                "value": "1",
            },
        )
        self.client.put(
            "/api/days/2026-07-23/summary",
            headers=self.alpha_headers,
            json={"content": "Closure remained optional and calm."},
        )
        for index in range(6):
            self.client.post(
                f"/api/days/2026-07-{18 + index}/carry-forward",
                headers=self.alpha_headers,
                json={"content": f"Alpha open thread {index}"},
            )
        self.client.post(
            "/api/days/2026-07-23/carry-forward",
            headers=self.beta_headers,
            json={"content": "Private beta thread"},
        )

        response = self.client.get(
            "/api/days/2026-07-23/closure",
            headers=self.alpha_headers,
        )

        self.assertEqual(response.status_code, 200)
        preview = response.json()
        self.assertEqual(preview["status"], "open")
        self.assertTrue(preview["capture"]["has_daily_note"])
        self.assertEqual(preview["capture"]["conversation_entries"], 2)
        self.assertEqual(preview["capture"]["completed_habits"], 1)
        self.assertEqual(preview["capture"]["checkin_fields"], 2)
        self.assertTrue(preview["summary"]["exists"])
        self.assertEqual(preview["open_thread_count"], 6)
        self.assertEqual(len(preview["open_threads"]), 5)
        self.assertNotIn("Private beta thread", str(preview))

    def test_carry_forward_inherits_until_completed_and_is_user_scoped(self) -> None:
        created = self.client.post(
            "/api/days/2026-07-23/carry-forward",
            headers=self.alpha_headers,
            json={"content": "Continue the security review"},
        )
        self.assertEqual(created.status_code, 201)
        item_id = created.json()["id"]

        inherited = self.client.get(
            "/api/days/2026-07-24/carry-forward",
            headers=self.alpha_headers,
        )
        self.assertEqual(
            [item["content"] for item in inherited.json()],
            ["Continue the security review"],
        )
        self.assertEqual(inherited.json()[0]["origin_date"], "2026-07-23")

        private_to_alpha = self.client.get(
            "/api/days/2026-07-24/carry-forward",
            headers=self.beta_headers,
        )
        self.assertEqual(private_to_alpha.json(), [])

        forbidden = self.client.patch(
            f"/api/days/2026-07-24/carry-forward/{item_id}",
            headers=self.beta_headers,
            json={"status": "completed"},
        )
        self.assertEqual(forbidden.status_code, 404)

        completed = self.client.patch(
            f"/api/days/2026-07-24/carry-forward/{item_id}",
            headers=self.alpha_headers,
            json={"status": "completed"},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")

        later_day = self.client.get(
            "/api/days/2026-07-25/carry-forward",
            headers=self.alpha_headers,
        )
        self.assertEqual(later_day.json(), [])

    def test_user_cannot_toggle_another_users_habit(self) -> None:
        response = self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 2, "date": "2026-07-23", "value": "1"},
        )

        self.assertEqual(response.status_code, 404)

    def test_habit_lifecycle_preserves_history_and_user_ownership(self) -> None:
        created = self.client.post(
            "/api/habits",
            headers=self.alpha_headers,
            json={"name": "Deep Work"},
        )
        self.assertEqual(created.status_code, 201)
        habit_id = created.json()["id"]

        duplicate = self.client.post(
            "/api/habits",
            headers=self.alpha_headers,
            json={"name": "Deep Work"},
        )
        self.assertEqual(duplicate.status_code, 409)

        other_user_rename = self.client.patch(
            f"/api/habits/{habit_id}",
            headers=self.beta_headers,
            json={"name": "Stolen"},
        )
        self.assertEqual(other_user_rename.status_code, 404)

        renamed = self.client.patch(
            f"/api/habits/{habit_id}",
            headers=self.alpha_headers,
            json={"name": "Focused Work"},
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "Focused Work")

        completion = self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={
                "habit_id": habit_id,
                "date": "2026-07-23",
                "value": "1",
            },
        )
        self.assertEqual(completion.status_code, 200)

        archived = self.client.delete(
            f"/api/habits/{habit_id}", headers=self.alpha_headers
        )
        self.assertEqual(archived.status_code, 200)
        self.assertTrue(archived.json()["is_archived"])

        active_habits = self.client.get(
            "/api/habits", headers=self.alpha_headers
        )
        self.assertNotIn(
            habit_id, [habit["id"] for habit in active_habits.json()]
        )

        historical_month = self.client.get(
            "/api/habits/month?month=2026-07", headers=self.alpha_headers
        )
        historical_habit = next(
            habit
            for habit in historical_month.json()["habits"]
            if habit["id"] == habit_id
        )
        self.assertTrue(historical_habit["is_archived"])
        self.assertTrue(
            historical_month.json()["lookup"][f"{habit_id}-2026-07-23"]
        )

        archived_toggle = self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={
                "habit_id": habit_id,
                "date": "2026-07-24",
                "value": "1",
            },
        )
        self.assertEqual(archived_toggle.status_code, 404)

        reused_name = self.client.post(
            "/api/habits",
            headers=self.alpha_headers,
            json={"name": "Focused Work"},
        )
        self.assertEqual(reused_name.status_code, 201)

    def test_habit_completion_uses_day_spine_and_appears_in_month(self) -> None:
        response = self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 1, "date": "2026-07-23", "value": "1"},
        )
        day = self.client.get(
            "/api/days/2026-07-23", headers=self.alpha_headers
        )
        month = self.client.get(
            "/api/habits/month?month=2026-07", headers=self.alpha_headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(day.status_code, 200)
        self.assertTrue(month.json()["lookup"]["1-2026-07-23"])

    def test_checkin_values_are_bounded(self) -> None:
        response = self.client.put(
            "/api/days/2026-07-23/checkin",
            headers=self.alpha_headers,
            json={"energy_level": 8},
        )

        self.assertEqual(response.status_code, 422)

    def test_checkin_values_can_be_cleared_without_erasing_other_fields(
        self,
    ) -> None:
        created = self.client.put(
            "/api/days/2026-07-23/checkin",
            headers=self.alpha_headers,
            json={
                "energy_level": 4,
                "focus_quality": 3,
                "emotional_state": "Steady",
            },
        )
        cleared = self.client.put(
            "/api/days/2026-07-23/checkin",
            headers=self.alpha_headers,
            json={"energy_level": None, "emotional_state": None},
        )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.json()["energy_level"])
        self.assertIsNone(cleared.json()["emotional_state"])
        self.assertEqual(cleared.json()["focus_quality"], 3)

    def test_manual_summary_is_editable_and_source_traceable(self) -> None:
        self.client.put(
            "/api/days/2026-07-23",
            headers=self.alpha_headers,
            json={"daily_note": "Built the summary spine"},
        )
        saved = self.client.put(
            "/api/days/2026-07-23/summary",
            headers=self.alpha_headers,
            json={"content": "The continuity spine moved forward."},
        )
        fetched = self.client.get(
            "/api/days/2026-07-23/summary", headers=self.alpha_headers
        )

        self.assertEqual(saved.status_code, 200)
        self.assertTrue(saved.json()["is_user_edited"])
        self.assertEqual(
            fetched.json()["content"],
            "The continuity spine moved forward.",
        )
        self.assertEqual(len(fetched.json()["source_fingerprint"]), 64)
        self.assertFalse(fetched.json()["is_stale"])

    def test_summary_freshness_tracks_every_raw_source_type(self) -> None:
        target = "/api/days/2026-07-23"
        self.client.put(
            target,
            headers=self.alpha_headers,
            json={"daily_note": "Initial source"},
        )

        def save_and_expect_fresh() -> None:
            saved = self.client.put(
                f"{target}/summary",
                headers=self.alpha_headers,
                json={"content": "A user-authored continuity summary."},
            )
            self.assertFalse(saved.json()["is_stale"])

        def expect_stale() -> None:
            fetched = self.client.get(
                f"{target}/summary",
                headers=self.alpha_headers,
            )
            self.assertTrue(fetched.json()["is_stale"])

        save_and_expect_fresh()
        self.client.put(
            target,
            headers=self.alpha_headers,
            json={"daily_note": "Changed source"},
        )
        expect_stale()

        save_and_expect_fresh()
        self.client.put(
            f"{target}/checkin",
            headers=self.alpha_headers,
            json={"focus_quality": 4},
        )
        expect_stale()

        save_and_expect_fresh()
        self.client.post(
            f"{target}/conversation",
            headers=self.alpha_headers,
            json={"content": "A later raw trace"},
        )
        expect_stale()

        save_and_expect_fresh()
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={
                "habit_id": 1,
                "date": "2026-07-23",
                "value": "1",
            },
        )
        expect_stale()

    def test_recent_days_are_user_scoped_and_newest_first(self) -> None:
        self.client.put(
            "/api/days/2026-07-22",
            headers=self.alpha_headers,
            json={"daily_note": "Older thread"},
        )
        self.client.put(
            "/api/days/2026-07-23",
            headers=self.alpha_headers,
            json={"daily_note": "Current thread"},
        )
        self.client.put(
            "/api/days/2026-07-24",
            headers=self.beta_headers,
            json={"daily_note": "Private beta thread"},
        )

        response = self.client.get(
            "/api/days?limit=7", headers=self.alpha_headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [day["date"] for day in response.json()],
            ["2026-07-23", "2026-07-22"],
        )
        self.assertNotIn(
            "Private beta thread",
            [day["note_preview"] for day in response.json()],
        )

    def test_parallel_daily_panel_load_does_not_create_empty_day(self) -> None:
        paths = [
            "/api/days/2026-07-25",
            "/api/days/2026-07-25/habits",
            "/api/days/2026-07-25/closure",
            "/api/days/2026-07-25/context",
            "/api/days/2026-07-25/reentry",
            "/api/days/2026-07-25/checkin",
            "/api/days/2026-07-25/conversation",
            "/api/days/2026-07-25/summary",
            "/api/days/2026-07-25/carry-forward",
        ]

        def load(path: str):
            return self.client.get(path, headers=self.alpha_headers)

        with ThreadPoolExecutor(max_workers=len(paths)) as executor:
            responses = list(executor.map(load, paths, timeout=10))

        self.assertEqual(
            [response.status_code for response in responses],
            [200] * len(paths),
        )
        for path, response in zip(paths, responses):
            payload = response.json()
            if path.endswith(("/habits", "/conversation", "/carry-forward")):
                self.assertIsInstance(payload, list, path)
            elif path.endswith("/summary"):
                self.assertTrue(payload is None or isinstance(payload, dict), path)
            else:
                self.assertIsInstance(payload, dict, path)
            if path.endswith("/closure"):
                self.assertEqual(
                    set(payload),
                    {
                        "date",
                        "status",
                        "capture",
                        "summary",
                        "open_thread_count",
                        "open_threads",
                    },
                )
            elif path.endswith("/context"):
                self.assertEqual(set(payload), {"day", "previous_day"})
            elif path.endswith("/reentry"):
                self.assertEqual(
                    set(payload),
                    {"date", "previous_trace", "open_threads", "contexts"},
                )
        recent = self.client.get(
            "/api/days?limit=7", headers=self.alpha_headers
        )
        matching_days = [
            day for day in recent.json() if day["date"] == "2026-07-25"
        ]
        self.assertEqual(matching_days, [])
