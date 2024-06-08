import os
import psycopg2
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from sklearn.feature_extraction.text import TfidfVectorizer

from .stopwords import calculate_stop_words
educational_stopwords = [
    'курс', 'дисциплина', 'студент', 'система', 'метод', 'процесс', 'навык', 'работа', 'изучение', 'знание', 'задача',
    'технология', 'область', 'теория', 'принцип', 'исследование', 'course', 'управление', 'решение', 'применение',
    'цель', 'раздел', 'проектирование', 'данные', 'материал', 'структура', 'развитие', 'свойство', 'качество',
    'производство', 'модель', 'научный', 'построение', 'элемент', 'деятельность', 'характеристика', 'технологический',
    'обеспечение', 'расчёт', 'динамический', 'алгоритм', 'разработка', 'результат', 'создание', 'особенность',
    'лабораторный'
]

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
                        "filter": ["lowercase", "stop", "snowball", "english_stop", "russian_stop", "subject_stop"],
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
                    },
                    "subject_stop": {
                        "type": "stop",
                        "stopwords": educational_stopwords
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
            "_id": course_id,
            "_source": data
        }
        for course_id, data in courses.items()
    ]

    # Использование bulk API для индексации данных
    bulk(es, actions)


def prepare_courses(rows):
    course_data = {}
    for row in rows:
        course_id = row[0]
        title = row[1]
        description = row[2]
        section = row[3]
        topic = row[4]

        if course_id not in course_data:
            course_data[course_id] = {
                'title': title,
                'description': description,
                'sections': set(),
                'topics': set()
            }

        course_data[course_id]['sections'].add(section)
        course_data[course_id]['topics'].add(topic)

    # Преобразование set в list для JSON-совместимости
    for data in course_data.values():
        data['sections'] = list(data['sections'])
        data['topics'] = list(data['topics'])

    return course_data


def init():
    create_index(es, index_name=index_name)
    courses = fetch_courses()
    calculate_stop_words(courses)
    if courses:
        course_data = prepare_courses(courses)  # Агрегация данных
        index_courses(course_data)  # Индексация данных
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
            "text": f"{', '.join(top_hit['source']['sections'])}. {', '.join(top_hit['source']['topics'])}",
            "explanation": top_hit['explanation']
        }
    else:
        return {
            "text": "",
            "explanation": ""
        }
