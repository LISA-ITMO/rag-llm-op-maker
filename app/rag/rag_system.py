import os
import psycopg2
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from transformers import GPT2LMHeadModel, GPT2Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer

load_dotenv()

# Параметры подключения к Elasticsearch
es_host = os.getenv('ELASTICSEARCH_HOST', 'localhost')
elastic_password = os.getenv('ELASTIC_PASSWORD')
api_key = os.getenv('API_KEY')

vectorizer = TfidfVectorizer()
es = Elasticsearch([f"http://{es_host}:9200"], http_auth=('elastic', elastic_password))

# Создание индекса в Elasticsearch, если он еще не существует
index_name = "courses"

documents = [
    "the sky is blue",
    "the sun is bright",
    "the sun in the sky is bright",
    "we can see the shining sun, the bright sun"
]
# Обучение модели и преобразование документов в TF-IDF векторы
tfidf_matrix = vectorizer.fit_transform(documents)

# Результаты являются разреженной матрицей
print(tfidf_matrix)


def create_index(es, index_name):
    # Удаление индекса, если он уже существует
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)

    # Создание маппинга
    mapping = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "custom_standard_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop", "snowball", "english_stop", "russian_stop"],
                    }
                },
                "filter": {
                    "english_stop": {
                        "type": "stop",
                        "stopwords": "_english_"
                    },
                    "russian_stop": {
                        "type": "stop",
                        "stopwords": "_russian_"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "analyzer": "custom_standard_analyzer"
                },
                "description": {
                    "type": "text",
                    "analyzer": "custom_standard_analyzer"
                },
                "section": {
                    "type": "text",
                    "analyzer": "custom_standard_analyzer"
                },
                "topic": {
                    "type": "text",
                    "analyzer": "custom_standard_analyzer"
                }
            }
        }
    }

    # Создание индекса с нашим маппингом
    es.indices.create(index=index_name, body=mapping)


# Подключение к базе данных и извлечение данных
def fetch_courses():
    database_url = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    query = ("select wd.work_program_id, title as course_title, ww.description as course_description, "
             "name as section, wt.description as section_topic "
             "from workprogramsapp_topic wt "
             "join workprogramsapp_disciplinesection wd on wd.id = wt.discipline_section_id "
             "join workprogramsapp_expertise we on wd.work_program_id = we.work_program_id "
             "join workprogramsapp_workprogram ww on wd.work_program_id = ww.id "
             "where work_status = 'a'")
    cursor.execute(query)
    courses = cursor.fetchall()
    cursor.close()
    conn.close()
    return courses


# Индексация данных в Elasticsearch
def index_courses(courses):
    actions = [
        {
            "_index": index_name,
            "_id": work_program_id,
            "_source": {
                "id": work_program_id,
                "title": course_title,
                "description": course_description,
                "section": section,
                "topic": section_topic
            }
        }
        for work_program_id, course_title, course_description, section, section_topic in courses
    ]

    # Использование bulk API для индексации данных
    bulk(es, actions)


def init():
    create_index(es, index_name=index_name)
    courses = fetch_courses()
    if courses:
        index_courses(courses)
        print("Courses indexed successfully!")


# Поиск в Elasticsearch
def search_courses(query):
    body = {
        "query": {
            "function_score": {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "title",
                            "description",
                            "section",
                            "topic"
                        ],
                        "type": "best_fields"
                    }
                },
                "functions": [
                    {
                        "filter": {"match": {"title": query}},
                        "weight": 3
                    },
                    {
                        "filter": {"match": {"description": query}},
                        "weight": 2
                    },
                    {
                        "filter": {"match": {"section": query}},
                        "weight": 1.5
                    },
                    {
                        "filter": {"match": {"topic": query}},
                        "weight": 1
                    }
                ],
                "score_mode": "sum",  # Определяет, как итоговые счета функций должны быть суммированы
                "boost_mode": "multiply"  # Определяет, как итоговый функциональный счет влияет на счет запроса
            }
        },
        "explain": True,  # Включаем объяснение для каждого документа
        "size": 10  # Количество возвращаемых документов
    }

    response = es.search(index=index_name, body=body)
    results = []
    for hit in response['hits']['hits']:
        result_info = {
            'source': hit['_source'],
            'score': hit['_score'],
            'explanation': hit.get('_explanation', {})  # Добавляем объяснение в вывод, если доступно
        }
        results.append(result_info)
    return results


# Генерация текста с использованием GPT-2
def generate_text(prompt):
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    model = GPT2LMHeadModel.from_pretrained('gpt2')
    inputs = tokenizer.encode(prompt, return_tensors='pt')
    outputs = model.generate(inputs, max_length=500, num_return_sequences=1)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def generate_text_with_chatgpt(prompt):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
    )
    return response.json()['choices'][0]['message']['content']


init()


# Интеграция ретривера и генератора
def rag_system(query):
    hits = search_courses(query)
    if hits:
        top_hit = hits[0]  # Используем первый результат поиска
        return {
            "text": f"{top_hit['source']['title']}. {top_hit['source']['description']}",
            "explanation": top_hit['explanation']
        }
    else:
        return {
            "text": "No relevant courses found.",
            "explanation": ""
        }
