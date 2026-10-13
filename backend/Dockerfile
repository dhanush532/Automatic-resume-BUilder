FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 worker && chown -R worker:worker /app
USER worker
CMD ["uv", "run", "--no-sync", "celery", "-A", "app.workers.email:celery_app", "worker", "--loglevel=INFO", "--queues=emails_auth,emails_default", "--concurrency=2"]
