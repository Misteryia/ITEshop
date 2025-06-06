from elasticsearch import AsyncElasticsearch
from datetime import datetime, timedelta

class IndexManager:
    def __init__(self):
        self.client = AsyncElasticsearch(
            "http://ELASTICSEARCH:9200",
        )
        
    async def setup_index_lifecycle(self):
        # Создаем политику
        policy = {
            "policy": {
                "phases": {
                    "hot": {
                        "min_age": "0ms",
                        "actions": {
                            "rollover": {
                                "max_age": "7d",
                                "max_size": "50gb"
                            }
                        }
                    },
                    "delete": {
                        "min_age": "30d",
                        "actions": {
                            "delete": {}
                        }
                    }
                }
            }
        }
        
        # Применяем политику
        await self.client.ilm.put_lifecycle(
            name="logs_policy",
            body=policy
        )
        
        # Создаем шаблон индекса
        template = {
            "index_patterns": ["logs-*"],
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "lifecycle.name": "logs_policy",
                "lifecycle.rollover_alias": "logs"
            }
        }
        
        await self.client.indices.put_template(
            name="logs_template",
            body=template
        )
    
    async def cleanup_old_indices(self, days=30):
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            # Получаем список всех индексов
            indices = await self.client.indices.get(index="logs-*")
            
            for index_name in indices:
                try:
                    # Удаляем старые документы
                    await self.client.delete_by_query(
                        index=index_name,
                        body={
                            "query": {
                                "range": {
                                    "timestamp": {
                                        "lte": cutoff_date.isoformat()
                                    }
                                }
                            }
                        }
                    )
                    # Обновляем индексы после удаления
                    await self.client.indices.refresh(index=index_name)
                except Exception as e:
                    print(f"Error cleaning up index {index_name}: {str(e)}")
                    continue
                    
            # Принудительно обновляем все индексы
            await self.client.indices.refresh(index="logs-*")
        except Exception as e:
            print(f"Error in cleanup_old_indices: {str(e)}")
            raise
    
    async def get_index_stats(self):
        return await self.client.indices.stats(index="logs-*") 