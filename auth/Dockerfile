FROM python:3.10-slim

WORKDIR /app

COPY ./auth/app /app
COPY ./common /app
COPY ./auth/requirements.txt /app/requirements.txt

RUN apt-get update && \
    apt-get install -y gcc python3-dev libpq-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get remove -y gcc python3-dev && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
