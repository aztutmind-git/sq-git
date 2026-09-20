# Deployed to Google Cloud Run. Uses Python 3.12 (not 3.14) deliberately —
# 3.12 has stable prebuilt wheels for every dependency here (psycopg, bcrypt,
# pydantic-core), avoiding the build-from-source issues hit during local
# setup on very new Python versions. This is independent of whatever Python
# version you run locally.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# build-essential is a safety net in case any dependency ever lacks a
# prebuilt wheel for this exact image — most of ours do have one, so this
# rarely actually gets used, but avoids a repeat of past build failures.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run sets $PORT at runtime and expects the container to listen on it —
# don't hardcode 8080 in the CMD itself, read the env var instead.
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
