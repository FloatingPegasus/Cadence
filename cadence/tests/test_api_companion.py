if __package__:
    from .api_test_context import (
        ApiTestCase,
        AsyncMock,
        User,
        ai_service,
        asyncio,
        httpx,
        patch,
        settings,
    )
else:
    from api_test_context import (
        ApiTestCase,
        AsyncMock,
        User,
        ai_service,
        asyncio,
        httpx,
        patch,
        settings,
    )

COMPLETION = "cadence.app.domains.companion.service.ai_service.chat_with_fallback"
DAY = "2026-07-24"


class CadenceCompanionApiTests(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        settings.ai_enabled = True

    def log(self, content: str, *, reply: bool = True, headers=None, hour=15):
        return self.client.post(
            f"/api/days/{DAY}/logs",
            headers=headers or self.alpha_headers,
            json={"content": content, "hour": hour, "reply": reply},
        )

    def test_reply_is_saved_after_the_log_with_layered_context(self) -> None:
        self.client.post(
            "/api/goals",
            headers=self.alpha_headers,
            json={"kind": "long_term", "title": "Ship Cadence"},
        )
        self.client.post(
            "/api/habits/toggle",
            headers=self.alpha_headers,
            json={"habit_id": 1, "date": DAY, "value": "1"},
        )
        self.client.post(
            "/api/tasks",
            headers=self.alpha_headers,
            json={"title": "Send the invoice", "due_date": DAY},
        )
        self.log("Standup ran long", reply=False, hour=10)

        with patch(COMPLETION, new_callable=AsyncMock) as completion:
            completion.return_value = {"content": "  Start with the intro.  "}
            response = self.log("Stuck on the pitch deck")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["log"]["content"], "Stuck on the pitch deck")
        self.assertEqual(body["reply"]["role"], "assistant")
        self.assertEqual(body["reply"]["content"], "Start with the intro.")
        self.assertEqual(body["reply"]["hour"], 15)
        self.assertIsNone(body["notice"])

        kwargs = completion.await_args.kwargs
        self.assertEqual(kwargs["task"], "reply")
        self.assertEqual(kwargs["user_id"], 1)
        rules, context, log = kwargs["messages"]
        self.assertIn("two to four sentences", rules["content"])
        self.assertIn("no emoji", rules["content"])
        self.assertEqual(log, {"role": "user", "content": "Stuck on the pitch deck"})
        for expected in (
            "Goals:\n- Long term: Ship Cadence",
            "Habits:\n- Read: done",
            "Tasks:\n- Send the invoice (due today)",
            "Today:\nThey at 10 AM: Standup ran long",
        ):
            self.assertIn(expected, context["content"])
        self.assertNotIn("pitch deck", context["content"])

        thread = self.client.get(f"/api/days/{DAY}/logs", headers=self.alpha_headers)
        self.assertEqual(
            [entry["role"] for entry in thread.json()],
            ["user", "user", "assistant"],
        )

    def test_save_only_and_missing_consent_skip_the_model(self) -> None:
        with patch(COMPLETION, new_callable=AsyncMock) as completion:
            saved = self.log("Just noting this", reply=False)
            no_consent = self.log("Beta has AI off", headers=self.beta_headers)

        completion.assert_not_awaited()
        self.assertEqual(saved.status_code, 201)
        self.assertIsNone(saved.json()["reply"])
        self.assertIsNone(saved.json()["notice"])
        self.assertIsNone(no_consent.json()["reply"])

    def test_guests_never_get_replies(self) -> None:
        async def make_beta_a_consenting_guest() -> None:
            async with self.session_factory() as db:
                beta = await db.get(User, 2)
                beta.is_guest = True
                beta.ai_processing_consent = True
                await db.commit()

        asyncio.run(make_beta_a_consenting_guest())
        with patch(COMPLETION, new_callable=AsyncMock) as completion:
            response = self.log("Guest log", headers=self.beta_headers)

        completion.assert_not_awaited()
        self.assertIsNone(response.json()["reply"])

    def test_daily_limit_keeps_the_log_and_says_so(self) -> None:
        with (
            patch.object(settings, "ai_daily_reply_limit", 1),
            patch(COMPLETION, new_callable=AsyncMock) as completion,
        ):
            completion.return_value = {"content": "One step."}
            first = self.log("First")
            second = self.log("Second")

        self.assertEqual(completion.await_count, 1)
        self.assertIsNotNone(first.json()["reply"])
        self.assertIsNone(second.json()["reply"])
        self.assertIn("replies for today", second.json()["notice"])
        self.assertEqual(second.json()["log"]["content"], "Second")

    def test_crisis_words_always_bring_the_resources_line(self) -> None:
        with (
            patch.object(settings, "crisis_resources", "Call 14416."),
            patch(COMPLETION, new_callable=AsyncMock) as completion,
        ):
            completion.return_value = {"content": "I'm here. Breathe slowly."}
            replied = self.log("I don’t want to live like this")
            saved_only = self.log("Thinking about self-harm", reply=False)
            calm = self.log("I killed it at the gym")

        self.assertEqual(
            replied.json()["reply"]["content"],
            "I'm here. Breathe slowly.\n\nCall 14416.",
        )
        self.assertEqual(saved_only.json()["notice"], "Call 14416.")
        self.assertNotIn("14416", calm.json()["reply"]["content"])

    def test_provider_failure_keeps_the_log(self) -> None:
        with patch(COMPLETION, new_callable=AsyncMock) as completion:
            completion.side_effect = ai_service.AIProvidersExhaustedError("down")
            response = self.log("Still logging")

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["reply"])
        self.assertIn("couldn't reply", response.json()["notice"])
        thread = self.client.get(f"/api/days/{DAY}/logs", headers=self.alpha_headers)
        self.assertEqual([entry["content"] for entry in thread.json()], ["Still logging"])

    def test_context_layers_are_capped(self) -> None:
        for index in range(25):
            self.log(f"{index:02d} " + "long entry " * 40, reply=False)
        for index in range(40):
            self.client.post(
                "/api/tasks",
                headers=self.alpha_headers,
                json={"title": f"Task {index} " + "x" * 150, "due_date": DAY},
            )

        with patch(COMPLETION, new_callable=AsyncMock) as completion:
            completion.return_value = {"content": "Pick one."}
            self.log("Too much today")

        context = completion.await_args.kwargs["messages"][1]["content"]
        tasks = context.split("Tasks:\n", 1)[1].split("\n\n", 1)[0]
        today = context.split("Today:\n", 1)[1]
        self.assertLessEqual(len(tasks), 1_200)
        self.assertLessEqual(len(today), 4_000)
        self.assertTrue(today.startswith("…"))
        self.assertIn("24 long entry", today)

    def test_fixed_model_skips_the_catalog(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "From Ollama."}}]},
            )

        async def run():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                async with self.session_factory() as db:
                    return await ai_service.chat_with_fallback(
                        db,
                        task="reply",
                        messages=[{"role": "user", "content": "hi"}],
                        client=client,
                    )

        with (
            patch.object(settings, "ai_model", "llama3.2"),
            patch.object(settings, "ai_provider", "ollama"),
        ):
            settings.ai_api_key = "local"
            result = asyncio.run(run())

        self.assertEqual(result["content"], "From Ollama.")
        self.assertEqual(result["model"], "llama3.2")
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].url.path.endswith("/chat/completions"))
