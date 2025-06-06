FROM python:3.10-slim
WORKDIR /app

COPY ./cart/app /app
COPY ./common /app
COPY ./cart/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
