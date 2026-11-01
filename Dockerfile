FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCOUT_MODE=all

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY web ./web
COPY benchmarks ./benchmarks
COPY examples ./examples

EXPOSE 8010
CMD ["sh", "-c", "uvicorn yai_scout.api.app:app --host 0.0.0.0 --port ${PORT:-8010}"]

