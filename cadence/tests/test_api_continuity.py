if __package__:
    from .api_test_context import ApiTestCase
else:
    from api_test_context import ApiTestCase


class CadenceContinuityApiTests(ApiTestCase):

    def test_weekly_continuity_is_bounded_and_user_scoped(self) -> None:
        self.client.put(
            "/api/days/2026-07-21",
            headers=self.alpha_headers,
            json={"daily_note": "Stabilized the continuity query"},
        )
        self.client.patch(
            "/api/days/2026-07-21/status",
            headers=self.alpha_headers,
            json={"status": "closed"},
        )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 1, "date": "2026-07-21", "value": "1"},
        )
        self.client.post(
            "/api/days/2026-07-18/carry-forward",
            headers=self.alpha_headers,
            json={"content": "Keep the database contract visible"},
        )
        for index in range(24):
            self.client.post(
                "/api/days/2026-07-19/carry-forward",
                headers=self.alpha_headers,
                json={"content": f"Bounded weekly thread {index}"},
            )
        self.client.put(
            "/api/days/2026-07-22",
            headers=self.beta_headers,
            json={"daily_note": "Private beta trace"},
        )
        self.client.post(
            "/api/days/2026-07-19/carry-forward",
            headers=self.beta_headers,
            json={"content": "Private beta weekly thread"},
        )

        response = self.client.get(
            "/api/continuity/weeks/2026-07-23",
            headers=self.alpha_headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["week_start"], "2026-07-20")
        self.assertEqual(payload["week_end"], "2026-07-26")
        self.assertEqual(len(payload["days"]), 7)
        self.assertEqual(payload["totals"]["active_days"], 1)
        self.assertEqual(payload["totals"]["closed_days"], 1)
        self.assertEqual(payload["totals"]["habit_completions"], 1)
        self.assertEqual(len(payload["open_threads"]), 20)
        serialized = str(payload)
        self.assertNotIn("Private beta trace", serialized)
        self.assertNotIn("Private beta weekly thread", serialized)

    def test_weekly_reflection_is_canonical_editable_and_source_traceable(
        self,
    ) -> None:
        self.client.put(
            "/api/days/2026-07-21",
            headers=self.alpha_headers,
            json={"daily_note": "Built the weekly reflection source"},
        )
        saved = self.client.put(
            "/api/continuity/weeks/2026-07-23/reflection",
            headers=self.alpha_headers,
            json={"content": "The continuity layer became more coherent."},
        )
        same_week = self.client.get(
            "/api/continuity/weeks/2026-07-26/reflection",
            headers=self.alpha_headers,
        )
        private = self.client.get(
            "/api/continuity/weeks/2026-07-23/reflection",
            headers=self.beta_headers,
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["week_start"], "2026-07-20")
        self.assertEqual(saved.json()["week_end"], "2026-07-26")
        self.assertFalse(saved.json()["is_stale"])
        self.assertEqual(saved.json()["id"], same_week.json()["id"])
        self.assertEqual(private.json(), None)

        self.client.put(
            "/api/days/2026-07-22",
            headers=self.alpha_headers,
            json={"daily_note": "A later weekly source trace"},
        )
        stale = self.client.get(
            "/api/continuity/weeks/2026-07-20/reflection",
            headers=self.alpha_headers,
        )
        self.assertTrue(stale.json()["is_stale"])

        refreshed = self.client.put(
            "/api/continuity/weeks/2026-07-25/reflection",
            headers=self.alpha_headers,
            json={"content": stale.json()["content"]},
        )
        self.assertFalse(refreshed.json()["is_stale"])

    def test_weekly_reflection_history_and_search_are_bounded_and_scoped(
        self,
    ) -> None:
        reflections = [
            ("2026-07-06", "Architecture decisions stayed restrained."),
            ("2026-07-13", "Retrieval became easier to navigate."),
            ("2026-07-20", "Bounded weekly retrieval is now available."),
        ]
        for anchor, content in reflections:
            self.client.put(
                f"/api/continuity/weeks/{anchor}/reflection",
                headers=self.alpha_headers,
                json={"content": content},
            )
        self.client.put(
            "/api/continuity/weeks/2026-07-20/reflection",
            headers=self.beta_headers,
            json={"content": "Private beta bounded weekly reflection."},
        )

        history = self.client.get(
            "/api/continuity/reflections?limit=2",
            headers=self.alpha_headers,
        )
        search = self.client.get(
            "/api/continuity/search",
            headers=self.alpha_headers,
            params={
                "q": "bounded weekly",
                "source": "weekly_reflections",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            },
        )

        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()), 2)
        self.assertEqual(
            [item["week_start"] for item in history.json()],
            ["2026-07-20", "2026-07-13"],
        )
        self.assertNotIn("Private beta", str(history.json()))
        self.assertEqual(search.status_code, 200)
        self.assertEqual(len(search.json()["results"]), 1)
        self.assertEqual(
            search.json()["results"][0]["source"],
            "weekly_reflections",
        )
        self.assertEqual(
            search.json()["results"][0]["date"],
            "2026-07-20",
        )
        self.assertNotIn("Private beta", str(search.json()))

    def test_monthly_reconstruction_is_bounded_meaningful_and_scoped(
        self,
    ) -> None:
        project = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        ).json()
        self.client.put(
            "/api/days/2026-07-01",
            headers=self.alpha_headers,
            json={"daily_note": "Established the monthly continuity source"},
        )
        self.client.put(
            "/api/days/2026-07-01/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.post(
            "/api/days/2026-07-15/conversation",
            headers=self.alpha_headers,
            json={"content": "A mid-month raw trace"},
        )
        self.client.put(
            "/api/days/2026-07-15/checkin",
            headers=self.alpha_headers,
            json={"energy_level": 4},
        )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={
                "habit_id": 1,
                "date": "2026-07-15",
                "value": "1",
            },
        )
        self.client.get(
            "/api/days/2026-07-20",
            headers=self.alpha_headers,
        )
        self.client.patch(
            "/api/days/2026-07-21/status",
            headers=self.alpha_headers,
            json={"status": "closed"},
        )
        self.client.put(
            "/api/continuity/weeks/2026-06-29/reflection",
            headers=self.alpha_headers,
            json={"content": "The opening week crossed into July."},
        )
        self.client.post(
            "/api/days/2026-06-30/carry-forward",
            headers=self.alpha_headers,
            json={"content": "Alpha thread visible in July"},
        )
        self.client.put(
            "/api/days/2026-07-10",
            headers=self.beta_headers,
            json={"daily_note": "Private beta monthly trace"},
        )
        self.client.post(
            "/api/days/2026-06-30/carry-forward",
            headers=self.beta_headers,
            json={"content": "Private beta monthly thread"},
        )

        response = self.client.get(
            "/api/continuity/months/2026-07",
            headers=self.alpha_headers,
        )
        self.assert_invalid_month("/api/continuity/months/2026-7")

        self.assertEqual(response.status_code, 200)
        month = response.json()
        self.assertEqual(month["month_start"], "2026-07-01")
        self.assertEqual(month["month_end"], "2026-07-31")
        self.assertEqual(
            [day["date"] for day in month["days"]],
            ["2026-07-01", "2026-07-15", "2026-07-21"],
        )
        self.assertEqual(month["totals"]["active_days"], 3)
        self.assertEqual(month["totals"]["closed_days"], 1)
        self.assertEqual(month["totals"]["habit_completions"], 1)
        self.assertEqual(month["totals"]["weekly_reflections"], 1)
        self.assertEqual(month["contexts"][0]["name"], "Cadence")
        self.assertEqual(
            month["weekly_reflections"][0]["week_start"],
            "2026-06-29",
        )
        self.assertNotIn("Private beta", str(month))

    def test_patterns_are_bounded_local_and_non_judgmental(self) -> None:
        project = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        ).json()
        for target_date in ("2026-07-01", "2026-07-03", "2026-07-12"):
            self.client.put(
                f"/api/days/{target_date}",
                headers=self.alpha_headers,
                json={"daily_note": f"Trace on {target_date}"},
            )
            self.client.put(
                f"/api/days/{target_date}/contexts",
                headers=self.alpha_headers,
                json={"context_ids": [project["id"]]},
            )
        self.client.put(
            "/api/days/2026-07-03/checkin",
            headers=self.alpha_headers,
            json={"energy_level": 4, "focus_quality": 3},
        )
        self.client.put(
            "/api/days/2026-07-02",
            headers=self.beta_headers,
            json={"daily_note": "Private beta pattern"},
        )

        response = self.client.get(
            "/api/continuity/patterns?anchor_date=2026-07-24&weeks=4",
            headers=self.alpha_headers,
        )
        self.assert_invalid_month(
            "/api/continuity/patterns?anchor_date=2026-07-24&weeks=20"
        )

        self.assertEqual(response.status_code, 200)
        patterns = response.json()
        self.assertEqual(patterns["weeks"], 4)
        self.assertEqual(len(patterns["weekly"]), 4)
        self.assertEqual(patterns["totals"]["recorded_days"], 3)
        self.assertIn("not scores", patterns["interpretation"])
        self.assertIn(
            "Recurring context",
            [item["title"] for item in patterns["observations"]],
        )
        self.assertIn(
            "Returns after gaps",
            [item["title"] for item in patterns["observations"]],
        )
        self.assertNotIn("Private beta", str(patterns))

    def test_context_month_reconstructs_prior_weekly_and_daily_movement(
        self,
    ) -> None:
        project = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        ).json()
        self.client.put(
            "/api/days/2026-06-28",
            headers=self.alpha_headers,
            json={"daily_note": "Prior context before July"},
        )
        self.client.put(
            "/api/days/2026-06-28/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.post(
            "/api/days/2026-06-28/carry-forward",
            headers=self.alpha_headers,
            json={"content": "Resume the context-month contract"},
        )
        self.client.put(
            "/api/days/2026-07-05",
            headers=self.alpha_headers,
            json={"daily_note": "First July project trace"},
        )
        self.client.put(
            "/api/days/2026-07-05/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.patch(
            "/api/days/2026-07-05/status",
            headers=self.alpha_headers,
            json={"status": "closed"},
        )
        self.client.post(
            "/api/days/2026-07-18/conversation",
            headers=self.alpha_headers,
            json={"content": "Second July project trace"},
        )
        self.client.put(
            "/api/days/2026-07-18/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={
                "habit_id": 1,
                "date": "2026-07-18",
                "value": "1",
            },
        )

        response = self.client.get(
            f"/api/contexts/{project['id']}/months/2026-07",
            headers=self.alpha_headers,
        )
        forbidden = self.client.get(
            f"/api/contexts/{project['id']}/months/2026-07",
            headers=self.beta_headers,
        )
        self.assert_invalid_month(
            f"/api/contexts/{project['id']}/months/2026-7"
        )

        self.assertEqual(response.status_code, 200)
        context_month = response.json()
        self.assertEqual(context_month["context"]["name"], "Cadence")
        self.assertEqual(context_month["totals"]["active_days"], 2)
        self.assertEqual(context_month["totals"]["closed_days"], 1)
        self.assertEqual(context_month["totals"]["habit_completions"], 1)
        self.assertEqual(context_month["totals"]["conversation_entries"], 1)
        self.assertEqual(len(context_month["weeks"]), 2)
        self.assertEqual(
            context_month["previous_activity"]["date"],
            "2026-06-28",
        )
        self.assertEqual(
            context_month["open_threads"][0]["content"],
            "Resume the context-month contract",
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_discipline_month_reconstructs_completion_trace_and_is_scoped(
        self,
    ) -> None:
        project = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        ).json()
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 1, "date": "2026-06-28", "value": "1"},
        )
        self.client.put(
            "/api/days/2026-06-28",
            headers=self.alpha_headers,
            json={"daily_note": "Prior reading trace"},
        )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 1, "date": "2026-07-05", "value": "1"},
        )
        self.client.put(
            "/api/days/2026-07-05/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.put(
            "/api/days/2026-07-05",
            headers=self.alpha_headers,
            json={"daily_note": "First reading trace"},
        )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 1, "date": "2026-07-18", "value": "1"},
        )
        self.client.post(
            "/api/days/2026-07-18/conversation",
            headers=self.alpha_headers,
            json={"content": "Reading thread"},
        )

        response = self.client.get(
            "/api/habits/1/months/2026-07",
            headers=self.alpha_headers,
        )
        forbidden = self.client.get(
            "/api/habits/1/months/2026-07",
            headers=self.beta_headers,
        )
        self.assert_invalid_month("/api/habits/1/months/2026-7")

        self.assertEqual(response.status_code, 200)
        discipline_month = response.json()
        self.assertEqual(discipline_month["discipline"]["name"], "Read")
        self.assertEqual(discipline_month["totals"]["completed_days"], 2)
        self.assertEqual(discipline_month["totals"]["linked_trace_days"], 2)
        self.assertEqual(discipline_month["totals"]["contexts"], 1)
        self.assertEqual(
            discipline_month["previous_completion"]["date"],
            "2026-06-28",
        )
        self.assertEqual(
            [day["date"] for day in discipline_month["days"]],
            ["2026-07-05", "2026-07-18"],
        )
        self.assertEqual(discipline_month["contexts"][0]["completed_days"], 1)
        self.assertEqual(forbidden.status_code, 404)

    def test_account_export_is_complete_deterministic_and_user_scoped(
        self,
    ) -> None:
        project = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        ).json()
        self.client.put(
            "/api/days/2026-07-24",
            headers=self.alpha_headers,
            json={"daily_note": "Alpha portable daily trace"},
        )
        self.client.put(
            "/api/days/2026-07-24/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.put(
            "/api/days/2026-07-24/checkin",
            headers=self.alpha_headers,
            json={"energy_level": 4, "notes": "Portable check-in"},
        )
        self.client.post(
            "/api/days/2026-07-24/conversation",
            headers=self.alpha_headers,
            json={"content": "Portable quick thread"},
        )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 1, "date": "2026-07-24", "value": "1"},
        )
        self.client.put(
            "/api/days/2026-07-24/summary",
            headers=self.alpha_headers,
            json={"content": "Portable manual summary"},
        )
        self.client.post(
            "/api/days/2026-07-24/carry-forward",
            headers=self.alpha_headers,
            json={"content": "Portable open thread"},
        )
        self.client.put(
            "/api/continuity/weeks/2026-07-24/reflection",
            headers=self.alpha_headers,
            json={"content": "Portable weekly reflection"},
        )
        self.client.put(
            "/api/days/2026-07-24",
            headers=self.beta_headers,
            json={"daily_note": "Private beta trace"},
        )

        response = self.client.get(
            "/api/account/export",
            headers=self.alpha_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "cadence-export-",
            response.headers["content-disposition"],
        )
        exported = response.json()
        resources = exported["resources"]
        self.assertEqual(exported["format"], "cadence-export")
        self.assertEqual(exported["schema_version"], 1)
        self.assertEqual(exported["account"]["username"], "alpha")
        self.assertEqual(
            [habit["name"] for habit in resources["habits"]],
            ["Read"],
        )
        self.assertEqual(resources["days"][0]["date"], "2026-07-24")
        self.assertEqual(
            resources["conversation_entries"][0]["content"],
            "Portable quick thread",
        )
        self.assertEqual(
            resources["weekly_reflections"][0]["content"],
            "Portable weekly reflection",
        )
        self.assertNotIn("hashed_password", str(exported))
        self.assertNotIn("Private beta trace", str(exported))

    def test_continuity_search_is_scoped_filtered_and_bounded(self) -> None:
        self.client.put(
            "/api/days/2026-07-21",
            headers=self.alpha_headers,
            json={"daily_note": "Continuity search began with a daily note"},
        )
        self.client.post(
            "/api/days/2026-07-21/conversation",
            headers=self.alpha_headers,
            json={"content": "The continuity query stayed relational"},
        )
        self.client.put(
            "/api/days/2026-07-21/summary",
            headers=self.alpha_headers,
            json={"content": "Continuity retrieval is now source traceable"},
        )
        self.client.post(
            "/api/days/2026-07-21/carry-forward",
            headers=self.alpha_headers,
            json={"content": "Review continuity search limits"},
        )
        self.client.put(
            "/api/days/2026-07-22",
            headers=self.beta_headers,
            json={"daily_note": "Private continuity result"},
        )

        response = self.client.get(
            "/api/continuity/search",
            headers=self.alpha_headers,
            params={
                "q": "continuity",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
                "limit": 20,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            {result["source"] for result in payload["results"]},
            {"notes", "conversation", "summaries", "threads"},
        )
        self.assertNotIn("Private continuity result", str(payload))

        notes_only = self.client.get(
            "/api/continuity/search",
            headers=self.alpha_headers,
            params={
                "q": "continuity",
                "source": "notes",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            },
        )
        self.assertEqual(len(notes_only.json()["results"]), 1)
        self.assertEqual(notes_only.json()["results"][0]["source"], "notes")

        limited = self.client.get(
            "/api/continuity/search",
            headers=self.alpha_headers,
            params={
                "q": "continuity",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
                "limit": 2,
            },
        )
        self.assertEqual(len(limited.json()["results"]), 2)

        literal_wildcards = self.client.get(
            "/api/continuity/search",
            headers=self.alpha_headers,
            params={
                "q": "_%",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            },
        )
        self.assertEqual(literal_wildcards.json()["results"], [])

        oversized_range = self.client.get(
            "/api/continuity/search",
            headers=self.alpha_headers,
            params={
                "q": "continuity",
                "start_date": "2025-01-01",
                "end_date": "2026-07-31",
            },
        )
        self.assertEqual(oversized_range.status_code, 422)

    def test_context_lifecycle_preserves_history_and_ownership(self) -> None:
        created = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        )
        self.assertEqual(created.status_code, 201)
        context_id = created.json()["id"]

        duplicate = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "area"},
        )
        self.assertEqual(duplicate.status_code, 409)

        same_name_other_user = self.client.post(
            "/api/contexts",
            headers=self.beta_headers,
            json={"name": "Cadence", "kind": "learning"},
        )
        self.assertEqual(same_name_other_user.status_code, 201)

        cross_user_assignment = self.client.put(
            "/api/days/2026-07-21/contexts",
            headers=self.beta_headers,
            json={"context_ids": [context_id]},
        )
        self.assertEqual(cross_user_assignment.status_code, 404)

        assigned = self.client.put(
            "/api/days/2026-07-21/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [context_id]},
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()[0]["name"], "Cadence")

        renamed = self.client.patch(
            f"/api/contexts/{context_id}",
            headers=self.alpha_headers,
            json={"name": "Cadence Product", "kind": "project"},
        )
        self.assertEqual(renamed.status_code, 200)

        week = self.client.get(
            "/api/continuity/weeks/2026-07-21",
            headers=self.alpha_headers,
        )
        linked_day = next(
            day for day in week.json()["days"] if day["date"] == "2026-07-21"
        )
        self.assertEqual(
            linked_day["contexts"][0]["name"],
            "Cadence Product",
        )

        other_user_archive = self.client.delete(
            f"/api/contexts/{context_id}",
            headers=self.beta_headers,
        )
        self.assertEqual(other_user_archive.status_code, 404)

        archived = self.client.delete(
            f"/api/contexts/{context_id}",
            headers=self.alpha_headers,
        )
        self.assertEqual(archived.status_code, 200)
        self.assertTrue(archived.json()["is_archived"])

        active = self.client.get(
            "/api/contexts",
            headers=self.alpha_headers,
        )
        self.assertNotIn(
            context_id,
            [context["id"] for context in active.json()],
        )
        historical = self.client.get(
            "/api/days/2026-07-21/contexts",
            headers=self.alpha_headers,
        )
        self.assertTrue(historical.json()[0]["is_archived"])

        preserved = self.client.put(
            "/api/days/2026-07-21/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [context_id]},
        )
        self.assertEqual(preserved.status_code, 200)

        new_assignment = self.client.put(
            "/api/days/2026-07-22/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [context_id]},
        )
        self.assertEqual(new_assignment.status_code, 404)

    def test_context_hub_and_search_filter_reentry_without_leakage(self) -> None:
        project = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        ).json()
        learning = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Databases", "kind": "learning"},
        ).json()

        self.client.put(
            "/api/days/2026-07-21",
            headers=self.alpha_headers,
            json={"daily_note": "Reentry work for the Cadence interface"},
        )
        self.client.put(
            "/api/days/2026-07-21/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.post(
            "/api/days/2026-07-21/carry-forward",
            headers=self.alpha_headers,
            json={"content": "Finish the context reentry view"},
        )

        self.client.put(
            "/api/days/2026-07-22",
            headers=self.alpha_headers,
            json={"daily_note": "Reentry notes for database indexing"},
        )
        self.client.put(
            "/api/days/2026-07-22/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [learning["id"]]},
        )

        hub = self.client.get(
            f"/api/contexts/{project['id']}/continuity",
            headers=self.alpha_headers,
        )
        self.assertEqual(hub.status_code, 200)
        self.assertEqual(
            [day["date"] for day in hub.json()["recent_days"]],
            ["2026-07-21"],
        )
        self.assertEqual(
            hub.json()["open_threads"][0]["content"],
            "Finish the context reentry view",
        )
        self.assertNotIn("database indexing", str(hub.json()))

        other_user_hub = self.client.get(
            f"/api/contexts/{project['id']}/continuity",
            headers=self.beta_headers,
        )
        self.assertEqual(other_user_hub.status_code, 404)

        filtered_search = self.client.get(
            "/api/continuity/search",
            headers=self.alpha_headers,
            params={
                "q": "reentry",
                "context_id": project["id"],
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            },
        )
        self.assertEqual(filtered_search.status_code, 200)
        self.assertEqual(
            {result["date"] for result in filtered_search.json()["results"]},
            {"2026-07-21"},
        )

        other_user_filter = self.client.get(
            "/api/continuity/search",
            headers=self.beta_headers,
            params={
                "q": "reentry",
                "context_id": project["id"],
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            },
        )
        self.assertEqual(other_user_filter.status_code, 404)

    def test_day_reentry_is_bounded_relevant_and_user_scoped(self) -> None:
        project = self.client.post(
            "/api/contexts",
            headers=self.alpha_headers,
            json={"name": "Cadence", "kind": "project"},
        ).json()

        self.client.put(
            "/api/days/2026-07-20",
            headers=self.alpha_headers,
            json={"daily_note": "Established the first continuity trace"},
        )
        self.client.put(
            "/api/days/2026-07-20/summary",
            headers=self.alpha_headers,
            json={"content": "The continuity foundation was established."},
        )
        self.client.put(
            "/api/days/2026-07-20/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.put(
            "/api/days/2026-07-21",
            headers=self.alpha_headers,
            json={"daily_note": "Refined the bounded re-entry contract"},
        )
        self.client.put(
            "/api/days/2026-07-21/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )
        self.client.put(
            "/api/days/2026-07-23/contexts",
            headers=self.alpha_headers,
            json={"context_ids": [project["id"]]},
        )

        for day_number in range(19, 23):
            self.client.post(
                f"/api/days/2026-07-{day_number}/carry-forward",
                headers=self.alpha_headers,
                json={"content": f"Alpha thread {day_number}"},
            )
        self.client.put(
            "/api/days/2026-07-22",
            headers=self.beta_headers,
            json={"daily_note": "Private beta trace"},
        )
        self.client.post(
            "/api/days/2026-07-22/carry-forward",
            headers=self.beta_headers,
            json={"content": "Private beta thread"},
        )

        response = self.client.get(
            "/api/days/2026-07-23/reentry",
            headers=self.alpha_headers,
        )

        self.assertEqual(response.status_code, 200)
        reentry = response.json()
        self.assertEqual(reentry["previous_trace"]["date"], "2026-07-21")
        self.assertEqual(reentry["previous_trace"]["source"], "note")
        self.assertEqual(len(reentry["open_threads"]), 3)
        self.assertEqual(
            [item["content"] for item in reentry["open_threads"]],
            ["Alpha thread 22", "Alpha thread 21", "Alpha thread 20"],
        )
        self.assertNotIn("Private beta thread", str(reentry))
        self.assertEqual(reentry["contexts"][0]["name"], "Cadence")
        self.assertEqual(
            reentry["contexts"][0]["last_activity"]["date"],
            "2026-07-21",
        )
        self.assertIn(
            "bounded re-entry",
            reentry["contexts"][0]["last_activity"]["excerpt"],
        )
