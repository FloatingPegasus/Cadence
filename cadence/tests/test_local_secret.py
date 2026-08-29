import tempfile
import unittest
from pathlib import Path

from cadence.signing_key import INSECURE_SECRET_KEYS, resolve_signing_key


class LocalSecretTests(unittest.TestCase):
    def test_keeps_a_configured_secret(self) -> None:
        key = "a" * 40
        self.assertEqual(resolve_signing_key(current=key, store=Path("/tmp/unused")), key)

    def test_rejects_placeholders_and_persists_generated_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory) / "signing.key"
            first = resolve_signing_key(
                current="replace-with-a-long-random-value",
                store=store,
            )
            second = resolve_signing_key(current="", store=store)
            self.assertGreaterEqual(len(first), 32)
            self.assertNotIn(first, INSECURE_SECRET_KEYS)
            self.assertEqual(first, second)
            self.assertEqual(store.read_text(encoding="utf-8").strip(), first)
