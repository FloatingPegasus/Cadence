import asyncio
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import bcrypt
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cadence.app import app
from cadence.app.extensions import Base, configure_sqlite_engine, get_db
from cadence.app.persistence.models.habit import Habit
from cadence.app.persistence.models.ai_model import AIModel
from cadence.app.persistence.models.conversation_entry import ConversationEntry
from cadence.app.persistence.models.user import User
from cadence.app.config import settings
from cadence.app.services import ai as ai_service
from cadence.app.services.email import EmailDeliveryError
from cadence.app.web.routes.auth import _create_token


class CadenceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_dev_mode = settings.dev_mode
        self.original_test_mode = settings.test_mode
        self.original_dev_usernames = settings.dev_usernames
        self.original_ai_api_key = settings.ai_api_key
        self.original_ai_enabled = settings.ai_enabled
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.database_path = temp_file.name
        temp_file.close()

        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.database_path}"
        )
        configure_sqlite_engine(self.engine.sync_engine)
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

        async def prepare_database() -> None:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with self.session_factory() as db:
                password = bcrypt.hashpw(
                    b"test-password", bcrypt.gensalt()
                ).decode()
                db.add_all(
                    [
                        User(
                            id=1,
                            username="alpha",
                            email="alpha@example.com",
                            hashed_password=password,
                            is_verified=True,
                            ai_processing_consent=True,
                        ),
                        User(
                            id=2,
                            username="beta",
                            email="beta@example.com",
                            hashed_password=password,
                            is_verified=True,
                        ),
                    ]
                )
                await db.commit()
                db.add_all(
                    [
                        Habit(id=1, user_id=1, name="Read"),
                        Habit(id=2, user_id=2, name="Move"),
                    ]
                )
                await db.commit()

        asyncio.run(prepare_database())

        async def override_get_db():
            async with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.alpha_headers = {
            "Authorization": f"Bearer {_create_token(1)}"
        }
        self.beta_headers = {
            "Authorization": f"Bearer {_create_token(2)}"
        }

    def tearDown(self) -> None:
        settings.dev_mode = self.original_dev_mode
        settings.test_mode = self.original_test_mode
        settings.dev_usernames = self.original_dev_usernames
        settings.ai_api_key = self.original_ai_api_key
        settings.ai_enabled = self.original_ai_enabled
        self.client.close()
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        os.unlink(self.database_path)

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

    def test_dev_registry_uses_normal_login_plus_dev_mode(self) -> None:
        settings.dev_mode = True
        settings.dev_usernames = "alpha"
        settings.ai_api_key = ""
        alpha_me = self.client.get(
            "/api/auth/me", headers=self.alpha_headers
        )
        beta_me = self.client.get(
            "/api/auth/me", headers=self.beta_headers
        )
        response = self.client.get(
            "/api/dev/ai/models", headers=self.alpha_headers
        )
        self.assertTrue(alpha_me.json()["is_developer"])
        self.assertFalse(beta_me.json()["is_developer"])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])

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
        invalid = self.client.get(
            "/api/continuity/months/2026-7",
            headers=self.alpha_headers,
        )

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
        self.assertEqual(invalid.status_code, 422)

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
        invalid = self.client.get(
            "/api/continuity/patterns?anchor_date=2026-07-24&weeks=20",
            headers=self.alpha_headers,
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
        self.assertEqual(invalid.status_code, 422)

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
        invalid = self.client.get(
            f"/api/contexts/{project['id']}/months/2026-7",
            headers=self.alpha_headers,
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
        self.assertEqual(invalid.status_code, 422)

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
        invalid = self.client.get(
            "/api/habits/1/months/2026-7",
            headers=self.alpha_headers,
        )

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
        self.assertEqual(invalid.status_code, 422)

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
            responses = list(executor.map(load, paths))

        self.assertEqual([response.status_code for response in responses], [200] * len(paths))
        recent = self.client.get(
            "/api/days?limit=7", headers=self.alpha_headers
        )
        matching_days = [
            day for day in recent.json() if day["date"] == "2026-07-25"
        ]
        self.assertEqual(matching_days, [])

    def test_sqlite_integrity_policy_and_hot_path_indexes(self) -> None:
        async def inspect_database() -> tuple[dict[str, object], set[str]]:
            async with self.engine.connect() as connection:
                pragmas = {
                    name: (
                        await connection.exec_driver_sql(f"PRAGMA {name}")
                    ).scalar()
                    for name in ("journal_mode", "foreign_keys", "busy_timeout")
                }
                result = await connection.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'index'"
                    )
                )
                indexes = set(result.scalars())

            async with self.session_factory() as db:
                db.add(
                    ConversationEntry(
                        day_id=999_999,
                        role="user",
                        content="Must not become an orphan",
                    )
                )
                with self.assertRaises(IntegrityError):
                    await db.commit()
                await db.rollback()

            return pragmas, indexes

        pragmas, indexes = asyncio.run(inspect_database())

        self.assertEqual(pragmas["journal_mode"], "wal")
        self.assertEqual(pragmas["foreign_keys"], 1)
        self.assertEqual(pragmas["busy_timeout"], 5000)
        self.assertIn("ix_habits_user_archived_id", indexes)
        self.assertIn("ix_conversation_entries_day_created", indexes)
        self.assertIn("ix_carry_forward_status_origin", indexes)


if __name__ == "__main__":
    unittest.main()
