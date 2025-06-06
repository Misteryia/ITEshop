from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response
from typing import Dict, Any
import time
from functools import wraps

class BaseMetrics:
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metr: Dict[str, Any] = {}
        self._setup_metr()

    def _setup_metr(self):
        # Метрики для API
        self.metr['api_requests'] = Counter(
            'api_requests_total',
            'Total number of API requests',
            ['service', 'endpoint', 'method', 'status']
        )

        self.metr['api_duration'] = Histogram(
            'api_request_duration_seconds',
            'Time spent processing API requests',
            ['service', 'endpoint', 'method']
        )

        # Метрики для базы данных
        self.metr['db_operations'] = Counter(
            'db_operations_total',
            'Total number of database operations',
            ['service', 'operation', 'status']
        )

        self.metr['db_duration'] = Histogram(
            'db_operation_duration_seconds',
            'Time spent on database operations',
            ['service', 'operation']
        )

    def api_metr(self):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    response = await func(*args, **kwargs)
                    status = 'success'
                except Exception as e:
                    status = 'error'
                    raise e
                finally:
                    duration = time.time() - start_time
                    self.metr['api_requests'].labels(
                        service=self.service_name,
                        endpoint=func.__name__,
                        method='GET', 
                        status=status
                    ).inc()
                    
                    self.metr['api_duration'].labels(
                        service=self.service_name,
                        endpoint=func.__name__,
                        method='GET' 
                    ).observe(duration)
                return response
            return wrapper
        return decorator

    def db_metr(self, operation: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    status = 'success'
                except Exception as e:
                    status = 'error'
                    raise e
                finally:
                    duration = time.time() - start_time
                    self.metr['db_operations'].labels(
                        service=self.service_name,
                        operation=operation,
                        status=status
                    ).inc()
                    
                    self.metr['db_duration'].labels(
                        service=self.service_name,
                        operation=operation
                    ).observe(duration)
                return result
            return wrapper
        return decorator

    async def metr_endpoint(self):
        return Response(generate_latest(), media_type='text/plain') 

metr = BaseMetrics("")
metr_endpoint = metr.metr_endpoint
api_metr = metr.api_metr
db_metr = metr.db_metr