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
    'лабораторный', 'профессиональный', 'основа', 'анализ', 'проблема'
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
                'topics': set(),
                'title_lemmatized': lemmatize_text(title),
                'description_lemmatized': lemmatize_text(description),
                'sections_lemmatized': set(),
                'topics_lemmatized': set()
            }

        course_data[course_id]['sections'].add(section)
        course_data[course_id]['topics'].add(topic)
        course_data[course_id]['sections_lemmatized'].add(lemmatize_text(section))
        course_data[course_id]['topics_lemmatized'].add(lemmatize_text(topic))

    # Преобразование set в list для JSON-совместимости
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
                            # "title_lemmatized^3",
                            # "title^3",
                            "description_lemmatized^2",
                            "description^2",
                            "sections_lemmatized^1.5",
                            "sections^1.5",
                            "topics_lemmatized",
                            "topics"
                        ],
                        "type": "best_fields"
                    }
                },
                "functions": [
                    # {
                    #     "filter": {"match": {"title_lemmatized": query}},
                    #     "weight": 3
                    # },
                    {
                        "filter": {"match": {"description": query}},
                        "weight": 2
                    },
                    {
                        "filter": {"match": {"description_lemmatized": query}},
                        "weight": 2
                    },
                    {
                        "filter": {"match": {"sections": query}},
                        "weight": 2
                    },
                    {
                        "filter": {"match": {"sections_lemmatized": query}},
                        "weight": 1.5
                    },
                    {
                        "filter": {"match": {"topics": query}},
                        "weight": 1
                    },
                    {
                        "filter": {"match": {"topics_lemmatized": query}},
                        "weight": 1
                    }
                ],
                "score_mode": "sum",  # Определяет, как итоговые счета функций должны быть суммированы
                "boost_mode": "multiply"  # Определяет, как итоговый функциональный счет влияет на счет запроса
            }
        },
        "_source": ["title", "title_lemmatized", "description", "description_lemmatized", "sections",
                    "sections_lemmatized", "topics", "topics_lemmatized"],  # Указываем, какие поля нужно вернуть
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
