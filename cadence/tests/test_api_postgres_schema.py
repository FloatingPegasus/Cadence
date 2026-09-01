if __package__:
    from .api_test_context import (
        ApiTestCase,
        ConversationEntry,
        IntegrityError,
        asyncio,
        text,
        unittest,
    )
else:
    from api_test_context import (
        ApiTestCase,
        ConversationEntry,
        IntegrityError,
        asyncio,
        text,
        unittest,
    )


class CadencePostgresSchemaApiTests(ApiTestCase):

    def test_postgresql_integrity_policy_and_hot_path_indexes(self) -> None:
        async def inspect_database() -> tuple[bool, bool, set[str], str, str]:
            async with self.engine.connect() as connection:
                extension = await connection.scalar(
                    text(
                        "SELECT 1 FROM pg_extension "
                        "WHERE extname = 'vector'"
                    )
                )
                trgm_extension = await connection.scalar(
                    text(
                        "SELECT 1 FROM pg_extension "
                        "WHERE extname = 'pg_trgm'"
                    )
                )
                result = await connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = current_schema()"
                    )
                )
                indexes = set(result.scalars())
                vector_type = await connection.scalar(
                    text(
                        "SELECT format_type(a.atttypid, a.atttypmod) "
                        "FROM pg_attribute AS a "
                        "WHERE a.attrelid = "
                        "'continuity_embeddings'::regclass "
                        "AND a.attname = 'embedding' "
                        "AND a.attnum > 0 "
                        "AND NOT a.attisdropped"
                    )
                )
                index_definition = await connection.scalar(
                    text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE schemaname = current_schema() "
                        "AND indexname = "
                        "'ix_continuity_embeddings_embedding_hnsw'"
                    )
                )

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

            return (
                extension == 1,
                trgm_extension == 1,
                indexes,
                str(vector_type),
                str(index_definition),
            )

        (
            vector_extension_enabled,
            trgm_extension_enabled,
            indexes,
            vector_type,
            index_definition,
        ) = asyncio.run(inspect_database())

        self.assertTrue(vector_extension_enabled)
        self.assertTrue(trgm_extension_enabled)
        self.assertEqual(vector_type, "vector(1024)")
        self.assertIn("ix_habits_user_archived_id", indexes)
        self.assertIn("ix_conversation_entries_day_created", indexes)
        self.assertIn("ix_carry_forward_status_origin", indexes)
        self.assertIn("ix_continuity_embeddings_embedding_hnsw", indexes)
        self.assertIn("ix_days_daily_note_trgm", indexes)
        self.assertIn("ix_conversation_entries_content_trgm", indexes)
        self.assertIn("ix_summary_artifacts_content_trgm", indexes)
        self.assertIn("ix_carry_forward_items_content_trgm", indexes)
        self.assertIn("ix_weekly_reflections_content_trgm", indexes)
        self.assertIn("ix_hour_logs_day_id", indexes)
        self.assertIn("ix_user_goals_user_id", indexes)
        self.assertIn("ix_tasks_user_due", indexes)
        normalized_index_definition = index_definition.casefold()
        self.assertIn("using hnsw", normalized_index_definition)
        self.assertIn("vector_cosine_ops", normalized_index_definition)
        self.assertIn("where", normalized_index_definition)
        self.assertIn("is_current", normalized_index_definition)
        self.assertIn("true", normalized_index_definition)


if __name__ == "__main__":
    unittest.main()
