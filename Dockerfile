FROM python:3.12-slim

ARG APP_REVISION=unknown
ENV APP_REVISION=${APP_REVISION}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN python -m pip install --only-binary=:all: --require-hashes -r requirements/build.txt \
    && python -m pip install --only-binary=:all: --require-hashes -r requirements/runtime.txt \
    && python -m pip install --no-index --no-deps --no-build-isolation -e .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

