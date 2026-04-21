FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . /app

RUN python -m pip install --upgrade pip && \
    if [ -f /app/requirements.txt ]; then \
        python -m pip install -r /app/requirements.txt; \
    elif [ -f /app/backend/requirements.txt ]; then \
        python -m pip install -r /app/backend/requirements.txt; \
    else \
        echo "requirements.txt not found in /app or /app/backend" && exit 1; \
    fi

EXPOSE 8000

CMD ["sh", "-c", "if [ -d /app/backend/app ]; then APP_DIR=/app/backend; else APP_DIR=/app; fi; python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --app-dir ${APP_DIR}"]
