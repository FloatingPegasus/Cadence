SELECT 'CREATE DATABASE cadence_test OWNER ' || quote_ident(current_user)
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'cadence_test'
)
\gexec

\connect cadence_test

CREATE EXTENSION IF NOT EXISTS vector;
