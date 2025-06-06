from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk
from elasticsearch import ConnectionError

ES_URL = "http://elasticsearch_engine:9200"
PRODUCTS_INDEX = "products_catalog"

elastic_client = AsyncElasticsearch(
    hosts=["http://elasticsearch_engine:9200"],
    headers={
        "Accept": "application/vnd.elasticsearch+json; compatible-with=8",
        "Content-Type": "application/vnd.elasticsearch+json; compatible-with=8"
    },
    verify_certs=False,
    ssl_show_warn=False
)

async def setup_products_index():
    try:
        print(f"Проверка доступности Elasticsearch по адресу: {ES_URL}")
        exists = await elastic_client.indices.exists(index=PRODUCTS_INDEX)
        print(f"Индекс {PRODUCTS_INDEX} существует: {exists}")
    except ConnectionError as e:
        print(f"[ERROR] Elasticsearch недоступен: {e}")
        return
    except Exception as e:
        print(f"[ERROR] Непредвиденная ошибка при проверке индекса: {e}")
        return

    if not exists:
        print(f"Создание индекса {PRODUCTS_INDEX}")
        index_config = {
            "settings": {
                "analysis": {
                    "filter": {
                        "autocomplete_filter": {
                            "type": "edge_ngram",
                            "min_gram": 2,
                            "max_gram": 20
                        },
                        "russian_stop": {
                            "type": "stop",
                            "stopwords": "_russian_"
                        },
                        "russian_stemmer": {
                            "type": "stemmer",
                            "language": "russian"
                        }
                    },
                    "analyzer": {
                        "autocomplete": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "russian_stop",
                                "russian_stemmer",
                                "autocomplete_filter"
                            ]
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "name": {"type": "text", "analyzer": "autocomplete"},
                    "description": {
                        "type": "text", 
                        "analyzer": "autocomplete",
                        "search_analyzer": "standard"
                    },
                    "price": {"type": "float"},
                    "quantity": {"type": "integer"},
                    "available": {"type": "boolean"},
                    "category_id": {"type": "integer"},
                    "brand_id": {"type": "integer"}
                }
            }
        }
        await elastic_client.indices.create(index=PRODUCTS_INDEX, body=index_config)

async def add_product_to_index(product: dict):
    print(f"Индексируем продукт в Elastic: {product}")
    await elastic_client.index(index=PRODUCTS_INDEX, id=product["id"], document=product)

async def remove_product_from_index(product_id: int):
    try:
        await elastic_client.delete(index=PRODUCTS_INDEX, id=product_id)
    except NotFoundError:
        pass

async def find_products_by_query(query: str):
    search_body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["name", "description"],
                "fuzziness": "AUTO"
            }
        }
    }
    response = await elastic_client.search(index="products_catalog", body=search_body)
    
    print(f"Ищем в Elastic запрос: '{query}'")
    print("Ответ: ", response)
    hits = response["hits"]["hits"]
    return [hit["_source"] for hit in hits]