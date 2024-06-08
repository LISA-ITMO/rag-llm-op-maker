import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from langdetect import detect
import numpy as np
from pymorphy2 import MorphAnalyzer
import string
from sklearn.feature_extraction.text import TfidfVectorizer

# Загрузка стоп-слов
nltk.download('stopwords')
nltk.download('punkt')
russian_stopwords = stopwords.words('russian')
english_stopwords = stopwords.words('english')

# Инициализация анализатора для русского
morph_ru = MorphAnalyzer()


def preprocess_text(text):
    # Определение языка текста
    lang = detect(text)
    stop_words = russian_stopwords if lang == 'ru' else english_stopwords

    # Удаление знаков пунктуации
    text = "".join([char for char in text if char not in string.punctuation])

    # Токенизация
    words = word_tokenize(text, language='russian' if lang == 'ru' else 'english')

    # Лемматизация для русского и просто фильтрация стоп-слов для английского
    if lang == 'ru':
        words = [morph_ru.parse(word)[0].normal_form for word in words if word not in stop_words]
    else:
        words = [word.lower() for word in words if word.lower() not in stop_words]

    return " ".join(words)


def calculate_stop_words(courses):
    documents = [
        preprocess_text(f"{course[2]} {course[3]} {course[4]}")
        for course in courses
    ]
    # Создание объекта TF-IDF векторизатора
    vectorizer = TfidfVectorizer()
    vectorizer.fit_transform(documents)

    # Получение массива IDF значений
    idf_values = vectorizer.idf_
    # Получение списка слов
    words = vectorizer.get_feature_names_out()

    # Сортировка слов по убыванию их IDF значений
    sorted_indices = np.argsort(idf_values)
    sorted_words = [words[idx] for idx in sorted_indices]
    sorted_idfs = [idf_values[idx] for idx in sorted_indices]

    # Определение порога для выбора стоп-слов
    idf_threshold = np.median(idf_values)  # Медиана может быть хорошей отправной точкой

    # Фильтрация слов, которые имеют IDF ниже порога
    stop_words = [word for word, idf in zip(sorted_words, sorted_idfs) if idf <= idf_threshold]

    print("Proposed new stop words:", stop_words)
