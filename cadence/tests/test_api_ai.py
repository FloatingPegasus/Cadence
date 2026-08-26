if __package__:
    from .api_test_context import (
        AIModel,
        ApiTestCase,
        AsyncMock,
        AsyncSession,
        Habit,
        ai_service,
        async_sessionmaker,
        asyncio,
        configure_pgvector_async_engine,
        create_async_engine,
        httpx,
        patch,
        select,
        settings,
    )
else:
    from api_test_context import (
        AIModel,
        ApiTestCase,
        AsyncMock,
        AsyncSession,
        Habit,
        ai_service,
        async_sessionmaker,
        asyncio,
        configure_pgvector_async_engine,
        create_async_engine,
        httpx,
        patch,
        select,
        settings,
    )


class CadenceAiApiTests(ApiTestCase):

    def test_dev_ai_registry_is_hidden_outside_dev_mode(self) -> None:
        response = self.client.get(
            "/api/dev/ai/models", headers=self.alpha_headers
        )
        self.assertEqual(response.status_code, 404)

    def test_nvidia_catalog_sync_ranks_and_filters_models(self) -> None:
        settings.ai_api_key = "test-key"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/models"):
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "z-ai/glm-5.2"},
                            {"id": "nvidia/nemotron-3-ultra-550b-a55b"},
                            {"id": "nvidia/nemotron-3-embed-1b"},
                            {"id": "example/new-chat-model"},
                        ]
                    },
                )
            return httpx.Response(404)

        async def sync_and_read():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                async with self.session_factory() as db:
                    result = await ai_service.sync_nvidia_catalog(
                        db, force=True, client=client
                    )
                    chain = await ai_service.fallback_chain(db, "context")
                    return result, chain

        result, chain = asyncio.run(sync_and_read())
        model_ids = [model["model_id"] for model in result["models"]]
        self.assertEqual(
            model_ids[:2],
            [
                "nvidia/nemotron-3-ultra-550b-a55b",
                "z-ai/glm-5.2",
            ],
        )
        self.assertNotIn("nvidia/nemotron-3-embed-1b", model_ids)
        self.assertEqual(
            chain[:2],
            [
                "nvidia/nemotron-3-ultra-550b-a55b",
                "z-ai/glm-5.2",
            ],
        )

    def test_concurrent_nvidia_catalog_refreshes_are_idempotent(self) -> None:
        settings.ai_api_key = "test-key"
        calls = 0
        ready = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            if request.url.path.endswith("/models"):
                calls += 1
                if calls == 2:
                    ready.set()
                await asyncio.wait_for(ready.wait(), timeout=10)
                return httpx.Response(
                    200,
                    request=request,
                    json={
                        "data": [
                            {"id": "01-ai/yi-large"},
                            {"id": "z-ai/glm-5.2"},
                        ]
                    },
                )
            return httpx.Response(404, request=request)

        async def refreshes():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                async def refresh():
                    async with self.session_factory() as db:
                        return await ai_service.sync_nvidia_catalog(
                            db, force=True, client=client
                        )

                return await asyncio.wait_for(
                    asyncio.gather(refresh(), refresh()),
                    timeout=10,
                )

        results = asyncio.run(refreshes())
        self.assertEqual(calls, 2)
        self.assertEqual(
            [
                [model["model_id"] for model in result["models"]]
                for result in results
            ],
            [
                ["z-ai/glm-5.2", "01-ai/yi-large"],
                ["z-ai/glm-5.2", "01-ai/yi-large"],
            ],
        )

    def test_catalog_freshness_read_releases_connection_before_provider(self) -> None:
        settings.ai_api_key = "test-key"

        async def run():
            engine = create_async_engine(
                settings.database_url,
                pool_size=2,
                max_overflow=0,
                pool_pre_ping=True,
            )
            configure_pgvector_async_engine(engine)
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            try:
                async with session_factory() as db:
                    observed = {}

                    async def handler(request: httpx.Request) -> httpx.Response:
                        if request.url.path.endswith("/models"):
                            observed["transaction"] = db.in_transaction()
                            observed["checked_out"] = (
                                engine.sync_engine.pool.checkedout()
                            )
                            await asyncio.sleep(0)
                            return httpx.Response(
                                200,
                                request=request,
                                json={"data": [{"id": "z-ai/glm-5.2"}]},
                            )
                        return httpx.Response(404, request=request)

                    async with httpx.AsyncClient(
                        transport=httpx.MockTransport(handler)
                    ) as client:
                        result = await ai_service.sync_nvidia_catalog(
                            db, force=True, client=client
                        )
                    return result, observed
            finally:
                await engine.dispose()

        result, observed = asyncio.run(run())
        self.assertFalse(observed["transaction"])
        self.assertEqual(observed["checked_out"], 0)
        self.assertEqual(
            [model["model_id"] for model in result["models"]],
            ["z-ai/glm-5.2"],
        )

    def test_catalog_freshness_supports_async_connection_bound_session(self) -> None:
        async def run():
            async with self.engine.connect() as connection:
                async with AsyncSession(bind=connection) as db:
                    latest = await ai_service._latest_nvidia_seen(db)
                    resolved, owns_engine = ai_service._caller_async_engine(db)
                    return latest, resolved, owns_engine

        latest, resolved, owns_engine = asyncio.run(run())
        self.assertIsNone(latest)
        self.assertIs(resolved, self.engine)
        self.assertFalse(owns_engine)

    def test_chat_http_barrier_releases_clean_caller_connection(self) -> None:
        settings.ai_enabled = True
        settings.ai_api_key = "test-key"

        async def run():
            async with self.session_factory() as seed_db:
                seed_db.add(
                    AIModel(
                        provider="nvidia",
                        model_id="pool-barrier-model",
                        strength_score=100,
                        ranking_version=ai_service.RANKING_VERSION,
                    )
                )
                await seed_db.commit()

            engine = create_async_engine(
                settings.database_url,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True,
            )
            configure_pgvector_async_engine(engine)
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            observed = {}

            async def handler(request: httpx.Request) -> httpx.Response:
                observed["caller_transaction"] = caller.in_transaction()
                observed["checked_out"] = engine.sync_engine.pool.checkedout()
                return httpx.Response(
                    200,
                    request=request,
                    json={
                        "choices": [{"message": {"content": "barrier ok"}}]
                    },
                )

            try:
                async with session_factory() as db:
                    caller = db
                    await db.scalar(select(Habit.id).where(Habit.id == 1))
                    async with httpx.AsyncClient(
                        transport=httpx.MockTransport(handler)
                    ) as client:
                        result = await ai_service.chat_with_fallback(
                            db,
                            task="summary",
                            messages=[
                                {"role": "user", "content": "hello"}
                            ],
                            client=client,
                            user_id=1,
                        )
                return result, observed
            finally:
                await engine.dispose()

        result, observed = asyncio.run(run())
        self.assertEqual(result["content"], "barrier ok")
        self.assertFalse(observed["caller_transaction"])
        self.assertEqual(observed["checked_out"], 0)

    def test_catalog_sync_rejects_direct_async_connection(self) -> None:
        settings.ai_api_key = "test-key"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                request=request,
                json={"data": [{"id": "z-ai/glm-5.2"}]},
            )

        async def run():
            async with self.engine.connect() as connection:
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(handler)
                ) as client:
                    with self.assertRaises(ai_service.AIConfigurationError):
                        await ai_service.sync_nvidia_catalog(
                            connection,
                            force=True,
                            client=client,
                        )

        asyncio.run(run())

    def test_catalog_refresh_rejects_pending_caller_transaction(self) -> None:
        settings.ai_api_key = "test-key"

        async def run():
            engine = create_async_engine(
                settings.database_url,
                pool_size=3,
                max_overflow=0,
                pool_pre_ping=True,
            )
            configure_pgvector_async_engine(engine)
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            observed = {"provider_reached": False}
            try:
                async with engine.connect() as connection:
                    async with AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                    ) as caller:
                        sentinel = Habit(
                            user_id=1,
                            name="caller-transaction-sentinel",
                        )
                        caller.add(sentinel)
                        await caller.flush()
                        observed["caller_transaction"] = caller.in_transaction()
                        observed["baseline_checked_out"] = (
                            engine.sync_engine.pool.checkedout()
                        )

                        async def handler(
                            request: httpx.Request,
                        ) -> httpx.Response:
                            observed["provider_reached"] = True
                            observed["caller_transaction"] = (
                                caller.in_transaction()
                            )
                            observed["checked_out_during_http"] = (
                                engine.sync_engine.pool.checkedout()
                            )
                            await asyncio.sleep(0)
                            return httpx.Response(
                                200,
                                request=request,
                                json={
                                    "data": [{"id": "z-ai/glm-5.2"}]
                                },
                            )

                        async with httpx.AsyncClient(
                            transport=httpx.MockTransport(handler)
                        ) as client:
                            with self.assertRaises(
                                ai_service.AIConfigurationError
                            ):
                                await ai_service.sync_nvidia_catalog(
                                    caller,
                                    force=True,
                                    client=client,
                                )

                        observed["caller_transaction_after"] = (
                            caller.in_transaction()
                        )
                        observed["caller_sentinel"] = await caller.get(
                            Habit,
                            sentinel.id,
                        )
                        async with session_factory() as observer:
                            observed["observer_sentinel"] = await observer.scalar(
                                select(Habit.id).where(
                                    Habit.id == sentinel.id
                                )
                            )
                            observed["observer_catalog"] = await observer.scalar(
                                select(AIModel.model_id).where(
                                    AIModel.provider == "nvidia",
                                    AIModel.model_id == "z-ai/glm-5.2",
                                )
                            )

                        await caller.rollback()
                        async with session_factory() as observer:
                            observed["after_rollback_sentinel"] = (
                                await observer.scalar(
                                    select(Habit.id).where(
                                        Habit.id == sentinel.id
                                    )
                                )
                            )
                            observed["after_rollback_catalog"] = (
                                await observer.scalar(
                                    select(AIModel.model_id).where(
                                        AIModel.provider == "nvidia",
                                        AIModel.model_id == "z-ai/glm-5.2",
                                    )
                                )
                            )
                        return observed
            finally:
                await engine.dispose()

        observed = asyncio.run(run())
        self.assertFalse(observed["provider_reached"])
        self.assertTrue(observed["caller_transaction"])
        self.assertTrue(observed["caller_transaction_after"])
        self.assertIsNotNone(observed["caller_sentinel"])
        self.assertIsNone(observed["observer_sentinel"])
        self.assertIsNone(observed["observer_catalog"])
        self.assertIsNone(observed["after_rollback_sentinel"])
        self.assertIsNone(observed["after_rollback_catalog"])

    def test_catalog_http_barrier_releases_connection_after_auth_query(self) -> None:
        settings.ai_api_key = "test-key"

        async def run():
            engine = create_async_engine(
                settings.database_url,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True,
            )
            configure_pgvector_async_engine(engine)
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            observed = {}

            async def handler(request: httpx.Request) -> httpx.Response:
                observed["provider_reached"] = True
                observed["caller_transaction"] = caller.in_transaction()
                observed["checked_out"] = engine.sync_engine.pool.checkedout()
                return httpx.Response(
                    200,
                    request=request,
                    json={"data": [{"id": "z-ai/glm-5.2"}]},
                )

            try:
                async with session_factory() as db:
                    caller = db
                    await db.scalar(select(Habit.id).where(Habit.id == 1))
                    async with httpx.AsyncClient(
                        transport=httpx.MockTransport(handler)
                    ) as client:
                        result = await ai_service.sync_nvidia_catalog(
                            db,
                            force=True,
                            client=client,
                        )
                return result, observed
            finally:
                await engine.dispose()

        result, observed = asyncio.run(run())
        self.assertTrue(observed["provider_reached"])
        self.assertFalse(observed["caller_transaction"])
        self.assertEqual(observed["checked_out"], 0)
        self.assertEqual(
            [model["model_id"] for model in result["models"]],
            ["z-ai/glm-5.2"],
        )

    def test_ai_completion_falls_back_after_rate_limit(self) -> None:
        settings.ai_enabled = True
        settings.ai_api_key = "test-key"
        outbound_messages = []

        async def prepare_models() -> None:
            async with self.session_factory() as db:
                db.add_all(
                    [
                        AIModel(
                            provider="nvidia",
                            model_id="nvidia/nemotron-3-ultra-550b-a55b",
                            strength_score=100,
                            ranking_version=ai_service.RANKING_VERSION,
                        ),
                        AIModel(
                            provider="nvidia",
                            model_id="z-ai/glm-5.2",
                            strength_score=98,
                            ranking_version=ai_service.RANKING_VERSION,
                        ),
                    ]
                )
                await db.commit()

        asyncio.run(prepare_models())

        def handler(request: httpx.Request) -> httpx.Response:
            payload = __import__("json").loads(request.content)
            outbound_messages.append(payload["messages"])
            model_id = payload["model"]
            if model_id.startswith("nvidia/"):
                return httpx.Response(429, json={"detail": "rate limited"})
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "Fallback succeeded"}}
                    ],
                    "usage": {"total_tokens": 12},
                },
            )

        async def complete():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                async with self.session_factory() as db:
                    return await ai_service.chat_with_fallback(
                        db,
                        task="context",
                        messages=[
                            {
                                "role": "user",
                                "content": (
                                    "Email alpha@example.com or call "
                                    "+1 (555) 123-4567 on 2026-07-24"
                                ),
                            }
                        ],
                        client=client,
                        user_id=1,
                    )

        result = asyncio.run(complete())
        self.assertEqual(result["model"], "z-ai/glm-5.2")
        self.assertEqual(result["content"], "Fallback succeeded")
        self.assertEqual(
            result["attempted_models"],
            ["nvidia/nemotron-3-ultra-550b-a55b", "z-ai/glm-5.2"],
        )
        self.assertTrue(result["redaction_applied"])
        self.assertNotIn("alpha@example.com", str(outbound_messages))
        self.assertNotIn("555", str(outbound_messages))
        self.assertIn("[redacted email]", str(outbound_messages))
        self.assertIn("[redacted phone]", str(outbound_messages))
        self.assertIn("2026-07-24", str(outbound_messages))

    def test_ai_preferences_default_private_and_gate_generation(self) -> None:
        settings.ai_enabled = True
        preferences = self.client.get(
            "/api/account/ai-preferences",
            headers=self.beta_headers,
        )
        self.client.put(
            "/api/days/2026-07-24",
            headers=self.beta_headers,
            json={"daily_note": "Keep this local"},
        )
        blocked = self.client.post(
            "/api/days/2026-07-24/summary/generate",
            headers=self.beta_headers,
            json={"replace_edited": False},
        )
        updated = self.client.put(
            "/api/account/ai-preferences",
            headers=self.beta_headers,
            json={
                "processing_consent": True,
                "redaction_enabled": False,
            },
        )
        me = self.client.get(
            "/api/auth/me",
            headers=self.beta_headers,
        )

        self.assertEqual(preferences.status_code, 200)
        self.assertFalse(preferences.json()["processing_consent"])
        self.assertTrue(preferences.json()["redaction_enabled"])
        self.assertEqual(blocked.status_code, 403)
        self.assertTrue(updated.json()["processing_consent"])
        self.assertFalse(updated.json()["redaction_enabled"])
        self.assertTrue(me.json()["ai_processing_consent"])
        self.assertFalse(me.json()["ai_redaction_enabled"])

    def test_ai_summary_records_model_and_protects_manual_edits(self) -> None:
        with patch(
            "cadence.app.domains.summaries.service.ai_service.chat_with_fallback",
            new_callable=AsyncMock,
        ) as completion:
            completion.return_value = {
                "provider": "nvidia",
                "model": "z-ai/glm-5.2",
                "content": "A concise generated continuity summary.",
            }
            generated = self.client.post(
                "/api/days/2026-07-23/summary/generate",
                headers=self.alpha_headers,
                json={"replace_edited": False},
            )

        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.json()["model"], "z-ai/glm-5.2")
        self.assertFalse(generated.json()["is_user_edited"])

        self.client.put(
            "/api/days/2026-07-23/summary",
            headers=self.alpha_headers,
            json={"content": "My edited interpretation"},
        )
        protected = self.client.post(
            "/api/days/2026-07-23/summary/generate",
            headers=self.alpha_headers,
            json={"replace_edited": False},
        )
        self.assertEqual(protected.status_code, 409)

    def test_ai_weekly_reflection_records_model_and_protects_edits(
        self,
    ) -> None:
        with patch(
            "cadence.app.domains.weekly_reflections.service."
            "ai_service.chat_with_fallback",
            new_callable=AsyncMock,
        ) as completion:
            completion.return_value = {
                "provider": "nvidia",
                "model": "z-ai/glm-5.2",
                "content": "A bounded generated weekly reflection.",
            }
            generated = self.client.post(
                "/api/continuity/weeks/2026-07-23/reflection/generate",
                headers=self.alpha_headers,
                json={"replace_edited": False},
            )

        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.json()["model"], "z-ai/glm-5.2")
        self.assertFalse(generated.json()["is_user_edited"])
        self.assertFalse(generated.json()["is_stale"])

        self.client.put(
            "/api/continuity/weeks/2026-07-23/reflection",
            headers=self.alpha_headers,
            json={"content": "My weekly interpretation"},
        )
        protected = self.client.post(
            "/api/continuity/weeks/2026-07-23/reflection/generate",
            headers=self.alpha_headers,
            json={"replace_edited": False},
        )
        self.assertEqual(protected.status_code, 409)
