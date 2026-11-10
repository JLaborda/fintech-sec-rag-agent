FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

# Fargate entry is overridden by Step Functions ContainerOverrides.
CMD ["python", "-m", "sec_signals.pipeline.fargate_index_emit_main", "--help"]
