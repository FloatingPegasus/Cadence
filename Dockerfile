FROM node:22-alpine AS frontend-build

WORKDIR /build/front
COPY front/package.json front/package-lock.json ./
RUN npm ci
COPY front/ ./
RUN npm run build

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN groupadd --system cadence \
    && useradd --system --gid cadence --create-home --home-dir /home/cadence cadence

RUN apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY cadence/requirements.txt /app/cadence/requirements.txt
RUN pip install --no-cache-dir -r /app/cadence/requirements.txt

COPY cadence/ /app/cadence/
COPY --from=frontend-build /build/front/dist /app/front/dist
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
COPY docker/wait_for_database.py /app/docker/wait_for_database.py
RUN mkdir -p /app/cadence/data/backups \
    && chmod 755 /app/docker/entrypoint.sh \
    && chown -R cadence:cadence /app

ENV HOME=/home/cadence
USER cadence

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
