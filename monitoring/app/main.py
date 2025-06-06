from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from routes import router
from kafka_consumer import KafkaLogConsumer
from index_manager import IndexManager
from elastic_client import ElasticClient
from metrics import api_metr, metr_endpoint
from tracing import setup_tracing
from trace_dec import trace_function
import asyncio
import logging
import jwt

app = FastAPI(
    title="Monitoring",
    description="Сервис для сбора и анализа логов, метрик и трейсов",
    version="1.0.0"
)

tracer = setup_tracing(app)

app.include_router(router)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return email
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

@app.get("/api/v1/protected")
@api_metr()
async def protected_route(current_user: str = Depends(get_current_user)):
    return {"message": f"Hello, {current_user}!"}

@app.on_event("startup")
@api_metr()
async def startup_event():
    try:
        # Инициализация политики хранения
        index_manager = IndexManager()
        await index_manager.setup_index_lifecycle()
    except Exception as e:
        logging.error(f"Failed to initialize index manager: {str(e)}")
        raise
    
    # Запуск Kafka consumer
    try:
        consumer = KafkaLogConsumer()
        # Запускаем consumer в фоне, чтобы не блокировать основной поток
        asyncio.create_task(consumer.start())
    except Exception as e:
        logging.error(f"Failed to start Kafka consumer: {str(e)}")
        raise

@app.on_event("shutdown")
@api_metr()
async def shutdown_event():
    try:
        # Остановка Kafka consumer
        consumer = KafkaLogConsumer()
        await consumer.stop()
    except Exception as e:
        logging.error(f"Failed to stop Kafka consumer: {str(e)}")
        raise

@app.get("/health")
@api_metr()
@trace_function(name="health_check", include_request=True)
async def health_check():
    return {"status": "healthy"}

@app.get("/metr")
@trace_function(name="get_metr", include_request=True)
async def get_metr():
    return await metr_endpoint()