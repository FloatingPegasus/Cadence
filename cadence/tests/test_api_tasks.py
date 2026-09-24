if __package__:
    from .api_test_context import (
        ApiTestCase,
        AsyncMock,
        ContinuityEmbedding,
        asyncio,
        patch,
        select,
        settings,
    )
else:
    from api_test_context import (
        ApiTestCase,
        AsyncMock,
        ContinuityEmbedding,
        asyncio,
        patch,
        select,
        settings,
    )

VECTOR = [1.0] + [0.0] * 1023


class CadenceTasksApiTests(ApiTestCase):
    def test_tasks_are_user_scoped_and_date_filtered(self) -> None:
        created = self.client.post(
            "/api/tasks",
            headers=self.alpha_headers,
            json={"title": "  Write the brief  ", "due_date": "2026-07-24"},
        )
        inbox = self.client.post(
            "/api/tasks",
            headers=self.alpha_headers,
            json={"title": "Someday"},
        )
        listed = self.client.get("/api/tasks", headers=self.alpha_headers)
        other = self.client.get("/api/tasks", headers=self.beta_headers)
        due = self.client.get(
            "/api/tasks?due_on=2026-07-24",
            headers=self.alpha_headers,
        )
        month = self.client.get(
            "/api/tasks?month=2026-07",
            headers=self.alpha_headers,
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["title"], "Write the brief")
        self.assertEqual(created.json()["due_date"], "2026-07-24")
        self.assertFalse(created.json()["is_completed"])
        self.assertFalse(created.json()["is_abandoned"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            [task["title"] for task in listed.json()],
            ["Write the brief", "Someday"],
        )
        self.assertEqual(other.json(), [])
        self.assertEqual(
            [task["title"] for task in due.json()],
            ["Write the brief"],
        )
        self.assertEqual(
            [task["title"] for task in month.json()],
            ["Write the brief"],
        )
        self.assertEqual(inbox.json()["due_date"], None)

    def test_task_completion_and_delete_stay_on_the_owner(self) -> None:
        created = self.client.post(
            "/api/tasks",
            headers=self.alpha_headers,
            json={"title": "Review the draft", "due_date": "2026-07-25"},
        )
        task_id = created.json()["id"]
        completed = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=self.alpha_headers,
            json={"is_completed": True},
        )
        foreign = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=self.beta_headers,
            json={"is_completed": False},
        )
        cleared = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=self.alpha_headers,
            json={"due_date": None, "is_completed": False},
        )
        deleted = self.client.delete(
            f"/api/tasks/{task_id}",
            headers=self.alpha_headers,
        )
        missing = self.client.get("/api/tasks", headers=self.alpha_headers)

        self.assertEqual(completed.status_code, 200)
        self.assertTrue(completed.json()["is_completed"])
        self.assertIsNotNone(completed.json()["completed_at"])
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(cleared.json()["due_date"], None)
        self.assertFalse(cleared.json()["is_completed"])
        self.assertIsNone(cleared.json()["completed_at"])
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(missing.json(), [])

    def test_abandoned_tasks_leave_the_open_list(self) -> None:
        created = self.client.post(
            "/api/tasks",
            headers=self.alpha_headers,
            json={"title": "Skip the meetup", "due_date": "2026-07-25"},
        )
        task_id = created.json()["id"]
        abandoned = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=self.alpha_headers,
            json={"is_abandoned": True},
        )
        restored = self.client.patch(
            f"/api/tasks/{task_id}",
            headers=self.alpha_headers,
            json={"is_abandoned": False},
        )

        self.assertEqual(abandoned.status_code, 200)
        self.assertTrue(abandoned.json()["is_abandoned"])
        self.assertFalse(abandoned.json()["is_completed"])
        self.assertEqual(restored.status_code, 200)
        self.assertFalse(restored.json()["is_abandoned"])

    def test_blank_task_title_is_rejected(self) -> None:
        response = self.client.post(
            "/api/tasks",
            headers=self.alpha_headers,
            json={"title": "   "},
        )
        self.assertEqual(response.status_code, 422)

    def test_tasks_join_the_search_index(self) -> None:
        settings.ai_enabled = True

        async def task_rows():
            async with self.session_factory() as db:
                rows = await db.scalars(
                    select(ContinuityEmbedding).where(
                        ContinuityEmbedding.source_type == "tasks"
                    )
                )
                return [(row.content, row.is_current) for row in rows]

        with (
            patch.object(settings, "embedding_enabled", True),
            patch(
                "cadence.app.services.embeddings.embed_text",
                new=AsyncMock(return_value=VECTOR),
            ),
        ):
            task_id = self.client.post(
                "/api/tasks",
                headers=self.alpha_headers,
                json={"title": "Call the bank"},
            ).json()["id"]
            indexed = asyncio.run(task_rows())
            self.client.patch(
                f"/api/tasks/{task_id}",
                headers=self.alpha_headers,
                json={"title": "Call the bank about the card"},
            )
            renamed = asyncio.run(task_rows())
            self.client.delete(f"/api/tasks/{task_id}", headers=self.alpha_headers)
            removed = asyncio.run(task_rows())

        self.assertEqual(indexed, [("Call the bank", True)])
        self.assertEqual(renamed, [("Call the bank about the card", True)])
        self.assertEqual(removed, [])
