import json
import os
import psycopg2
import requests
import pymorphy2
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

educational_stopwords = [
    'курс', 'дисциплина', 'студент', 'система', 'метод', 'процесс', 'навык', 'работа', 'изучение', 'знание', 'задача',
    'технология', 'область', 'теория', 'принцип', 'исследование', 'course', 'управление', 'решение', 'применение',
    'цель', 'раздел', 'проектирование', 'данные', 'материал', 'структура', 'развитие', 'свойство', 'качество',
    'производство', 'модель', 'научный', 'построение', 'элемент', 'деятельность', 'характеристика', 'технологический',
    'обеспечение', 'расчёт', 'динамический', 'алгоритм', 'разработка', 'результат', 'создание', 'особенность',
    'лабораторный', 'профессиональный', 'основа', 'анализ'
]

load_dotenv()

# Параметры подключения к Elasticsearch
es_host = os.getenv('ELASTICSEARCH_HOST', 'localhost')
elastic_password = os.getenv('ELASTIC_PASSWORD')
api_key = os.getenv('API_KEY')
es = Elasticsearch([f"http://{es_host}:9200"], http_auth=('elastic', elastic_password))

# Создание индекса в Elasticsearch, если он еще не существует
index_name = "courses"

morph = pymorphy2.MorphAnalyzer()


def lemmatize_text(text):
    if text is None:
        return ""
    words = text.split()  # Разбиение текста на слова
    lemmatized_words = [morph.parse(word)[0].normal_form for word in words]
    return ' '.join(lemmatized_words)  # Соединение слов обратно в строку


def create_index(es, index_name):
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)

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
                    "english_stop": {"type": "stop", "stopwords": "_english_"},
                    "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                    "subject_stop": {"type": "stop", "stopwords": educational_stopwords}
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "custom_standard_analyzer"},
                "description": {"type": "text", "analyzer": "custom_standard_analyzer"},
                "sections": {"type": "text", "analyzer": "custom_standard_analyzer"},
                "topics": {"type": "text", "analyzer": "custom_standard_analyzer"},
                "title_lemmatized": {"type": "text", "analyzer": "custom_standard_analyzer"},
                "description_lemmatized": {"type": "text", "analyzer": "custom_standard_analyzer"},
                "sections_lemmatized": {"type": "text", "analyzer": "custom_standard_analyzer"},
                "topics_lemmatized": {"type": "text", "analyzer": "custom_standard_analyzer"}
            }
        }
    }

    es.indices.create(index=index_name, body=mapping)


def load_mock_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, '../mock.json')
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def fetch_courses():
    data = load_mock_data()
    return data['courses']


# Индексация данных в Elasticsearch
def index_courses(courses):
    actions = [
        {
            "_index": index_name,
            "_id": course_id,
            "_source": details
        }
        for course_id, details in courses.items()
    ]

    # Использование bulk API для индексации данных
    bulk(es, actions)


def prepare_courses(rows):
    course_data = {}

    for row in rows:
        # Extract values directly from the dictionary
        course_id = str(row['id'])  # Convert to string if needed as a dictionary key
        title = row['title']
        description = row['description']
        sections = row['sections']  # This should be a list
        topics = row['topics']  # This should be a list

        # Initialize the dictionary for a new course_id
        if course_id not in course_data:
            course_data[course_id] = {
                'title': title,
                'description': description,
                'sections': set(),
                'topics': set(),
                'title_lemmatized': lemmatize_text(title),
                'description_lemmatized': lemmatize_text(description),
                'sections_lemmatized': set(),
                'topics_lemmatized': set()
            }

        # Add each section and topic to the sets for aggregation
        for section in sections:
            course_data[course_id]['sections'].add(section)
            course_data[course_id]['sections_lemmatized'].add(lemmatize_text(section))
        for topic in topics:
            course_data[course_id]['topics'].add(topic)
            course_data[course_id]['topics_lemmatized'].add(lemmatize_text(topic))

    # Convert sets to lists after all data has been processed for JSON compatibility
    for data in course_data.values():
        data['sections'] = list(data['sections'])
        data['topics'] = list(data['topics'])
        data['sections_lemmatized'] = list(data['sections_lemmatized'])
        data['topics_lemmatized'] = list(data['topics_lemmatized'])

    return course_data


def init():
    create_index(es, index_name=index_name)
    courses = fetch_courses()
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
                            "title_lemmatized^3",
                            "description_lemmatized^2",
                            "section_lemmatized^1.5",
                            "topic_lemmatized"
                        ],
                        "type": "best_fields"
                    }
                },
                "functions": [
                    {
                        "filter": {"match": {"title_lemmatized": query}},
                        "weight": 3
                    },
                    {
                        "filter": {"match": {"description_lemmatized": query}},
                        "weight": 2
                    },
                    {
                        "filter": {"match": {"section_lemmatized": query}},
                        "weight": 1.5
                    },
                    {
                        "filter": {"match": {"topic_lemmatized": query}},
                        "weight": 1
                    }
                ],
                "score_mode": "sum",  # Определяет, как итоговые счета функций должны быть суммированы
                "boost_mode": "multiply"  # Определяет, как итоговый функциональный счет влияет на счет запроса
            }
        },
        "_source": ["title", "description", "sections", "topics"],  # Указываем, какие поля нужно вернуть
        "size": 10,  # Количество возвращаемых документов
        "explain": True  # Включаем объяснение для каждого документа
    }

    response = es.search(index=index_name, body=body)
    results = []
    for hit in response['hits']['hits']:
        result_info = {
            'title': hit['_source']['title'],
            'description': hit['_source']['description'],
            'sections': hit['_source']['sections'],
            'topics': hit['_source']['topics'],
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
    hits = search_courses(query)  # убедитесь, что эта функция передаётся корректно и доступна в контексте
    if hits:
        top_hit = hits[0]  # Используем первый результат поиска
        # Обновлено для использования новой структуры данных
        return {
            "text": f"{', '.join(top_hit['sections'])}. {', '.join(top_hit['topics'])}",
            "explanation": top_hit['explanation']
        }
    else:
        return {
            "text": "",
            "explanation": ""
        }
