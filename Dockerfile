FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg binary and PDF processing
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install pip-installable project first (layer cache optimization)
COPY pyproject.toml .
RUN pip install --no-cache-dir uv \
    && uv pip install --system -e ".[dev]"

# Application source
COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
