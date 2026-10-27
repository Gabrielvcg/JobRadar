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
    && python -c 'from setuptools.build_meta import build_wheel; build_wheel("dist")' \
    && python -m pip install --only-binary=:all: --no-index --no-deps --find-links=dist jobradar==0.1.51

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

