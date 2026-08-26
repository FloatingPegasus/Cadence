"""Shared imports and helpers for the domain-focused API test modules."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

if __package__:
    from .bootstrap import configure_test_environment
else:
    from bootstrap import configure_test_environment

configure_test_environment()

import bcrypt
import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cadence.app import app
from cadence.app.config import settings
from cadence.app.extensions import configure_pgvector_async_engine
from cadence.app.persistence.models.ai_model import AIModel
from cadence.app.persistence.models.conversation_entry import ConversationEntry
from cadence.app.persistence.models.habit import Habit
from cadence.app.persistence.models.user import User
from cadence.app.services import ai as ai_service
from cadence.app.services.email import EmailDeliveryError
from cadence.app.web.routes.auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    _create_token,
    _decode_token,
)

if __package__:
    from .postgres_support import PostgresTestCase
else:
    from postgres_support import PostgresTestCase


class ApiTestCase(PostgresTestCase):
    """Small shared base for API domain tests."""

    def assert_invalid_month(self, path: str) -> None:
        response = self.client.get(path, headers=self.alpha_headers)
        self.assertEqual(response.status_code, 422)
