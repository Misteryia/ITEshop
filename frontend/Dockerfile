FROM python:3.10-slim

WORKDIR /app

COPY ./frontend/app /app
COPY ./common /app
COPY ./frontend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir \
    --default-timeout=300 \
    --retries=5 \
    -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
