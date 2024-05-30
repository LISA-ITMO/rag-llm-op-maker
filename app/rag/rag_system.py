import os
import psycopg2
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
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
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name)
        print(f"Index {index_name} created.")
    else:
        print(f"Index {index_name} already exists.")


# Подключение к базе данных и извлечение данных
def fetch_courses():
    database_url = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    cursor.execute(
        "select id, title, description from workprogramsapp_workprogram ww where work_status = 'a' and description <> ''")
    courses = cursor.fetchall()
    cursor.close()
    conn.close()
    return courses


# Индексация данных в Elasticsearch
def index_courses(courses):
    for id, title, description in courses:
        doc = {
            "id": id,
            "title": title,
            "description": description
        }
        es.index(index=index_name, body=doc)


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
            "multi_match": {
                "query": query,
                "fields": ["title", "description"]
            }
        }
    }
    response = es.search(index=index_name, body=body)
    return [hit["_source"] for hit in response['hits']['hits']]


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
        return f"{top_hit['title']}. {top_hit['description']}"
        # prompt = f"{top_hit['title']}. {top_hit['description']} What is this course about?"
        # return generate_text(prompt)
    else:
        return "No relevant courses found."
