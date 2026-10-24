FROM python:3.11-slim

WORKDIR /app

COPY config/ /app/config/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir -e /app/backend

EXPOSE 8000

CMD ["uvicorn", "backend.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
