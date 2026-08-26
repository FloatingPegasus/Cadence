# Cadence Architecture Diagrams

These diagrams describe the current FastAPI, PostgreSQL, pgvector, and pg_trgm
deployment. The browser uses the built frontend or the development server;
the API owns persistence and optional shared rate limiting.

## System architecture

```mermaid
graph LR
    Browser[Browser / React frontend]
    API[FastAPI application]
    DB[(PostgreSQL + pgvector + pg_trgm)]
    Redis[(Redis optional shared rate limits)]
    Provider[NVIDIA optional AI and embedding APIs]

    Browser -->|HTTP JSON| API
    API -->|SQLAlchemy psycopg| DB
    API -->|Shared auth limits when enabled| Redis
    API -->|Consent-gated requests| Provider
```

## Local Docker deployment

```mermaid
flowchart LR
    Compose[Docker Compose]
    Postgres[pgvector PostgreSQL container]
    App[Cadence API container]
    Volume[(PostgreSQL named volume)]
    Backups[(Backup volume)]

    Compose -->|healthcheck| Postgres
    Postgres -->|ready| App
    App -->|one-shot Alembic migration| Postgres
    App -->|runtime SQL| Postgres
    Postgres --- Volume
    App --- Backups
```

## Startup and migration flow

```mermaid
sequenceDiagram
    participant Compose
    participant DB as PostgreSQL
    participant App as Cadence container
    participant API as FastAPI

    Compose->>DB: Start pinned pgvector image
    DB-->>Compose: pg_isready healthcheck passes
    Compose->>App: Start after database health
    App->>DB: Authenticated SELECT 1 readiness probe
    App->>DB: Acquire migration advisory lock
    App->>DB: Alembic upgrade head
    App->>DB: Release migration advisory lock
    App->>API: Start Uvicorn
    API-->>Compose: /healthz returns 200 after DB probe
```

## Habit logging flow

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant API as FastAPI
    participant DB as PostgreSQL

    User->>Browser: Toggle a habit for a day
    Browser->>API: POST habit log JSON
    API->>DB: Validate user and upsert/delete log
    DB-->>API: Commit transaction
    API-->>Browser: JSON response
```

## Backup and restore flow

```mermaid
sequenceDiagram
    participant Operator
    participant CLI as Maintenance CLI
    participant DB as PostgreSQL
    participant Files as Backup volume

    Operator->>CLI: backup with direct connection URL
    CLI->>DB: pg_dump custom format
    CLI->>DB: pg_restore --list verification
    CLI->>Files: Atomically store verified .dump
    Operator->>CLI: stop all API replicas, then restore
    CLI->>DB: Create pre-restore safety dump
    CLI->>DB: pg_restore --single-transaction
    CLI->>Files: Retain safety dump for rollback
```
