FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCOUT_MODE=all \
    PORT=7860

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone --depth 1 https://github.com/Gi-Tuu/yai-scout /app
RUN pip install --no-cache-dir -e .

EXPOSE 7860
CMD ["sh", "-c", "uvicorn yai_scout.api.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
