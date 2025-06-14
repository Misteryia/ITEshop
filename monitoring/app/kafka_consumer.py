from aiokafka import AIOKafkaConsumer
import json
from log_processor import LogProcessor

class KafkaLogConsumer:
    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            'logs',
            'errors',
            bootstrap_servers="KAFKA:9092",
            group_id="MONITORING_GROUP",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            max_poll_interval_ms=300000
        )
        self.processor = LogProcessor()

    async def start(self):
        await self.consumer.start()
        try:
            async for message in self.consumer:
                try:
                    if message.topic == 'logs':
                        await self.processor.process_log(message.value)
                    elif message.topic == 'errors':
                        await self.processor.process_log(message.value, is_error=True)
                except Exception as e:
                    print(f"Error processing message from topic {message.topic}: {str(e)}")
                    # Продолжаем обработку следующих сообщений
                    continue
        except Exception as e:
            print(f"Fatal error in consumer: {str(e)}")
            raise
        finally:
            await self.consumer.stop()

    async def stop(self):
        await self.consumer.stop() 