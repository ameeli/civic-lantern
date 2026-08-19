FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock README.md ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

COPY . .

CMD ["uvicorn", "civic_lantern.main:app", "--host", "0.0.0.0", "--port", "8000"]
