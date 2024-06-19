import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from langdetect import detect
import numpy as np
from pymorphy2 import MorphAnalyzer
import string
from sklearn.feature_extraction.text import TfidfVectorizer

# Предварительная загрузка необходимых данных
nltk.download('stopwords')
nltk.download('punkt')

# Класс для предварительной обработки текстов
class TextPreprocessor:
    def __init__(self):
        self.russian_stopwords = stopwords.words('russian')
        self.english_stopwords = stopwords.words('english')
        self.morph_ru = MorphAnalyzer()

    def preprocess_text(self, text):
        try:
            lang = detect(text)
        except:
            lang = 'ru'  # По умолчанию используем русский, если язык не определен

        stop_words = self.russian_stopwords if lang == 'ru' else self.english_stopwords

        # Удаление знаков пунктуации
        text = text.translate(str.maketrans('', '', string.punctuation))

        # Токенизация
        words = word_tokenize(text, language='russian' if lang == 'ru' else 'english')

        # Лемматизация и фильтрация стоп-слов
        if lang == 'ru':
            words = [self.morph_ru.parse(word)[0].normal_form for word in words if word not in stop_words]
        else:
            words = [word.lower() for word in words if word.lower() not in stop_words]

        return " ".join(words)

# Класс для вычисления стоп-слов на основе IDF
class IDFStopWords:
    def __init__(self, documents):
        self.vectorizer = TfidfVectorizer()
        self.vectorizer.fit_transform(documents)

    def get_stop_words(self):
        idf_values = self.vectorizer.idf_
        words = self.vectorizer.get_feature_names_out()

        sorted_indices = np.argsort(idf_values)
        sorted_words = [words[idx] for idx in sorted_indices]
        sorted_idfs = [idf_values[idx] for idx in sorted_indices]

        idf_threshold = np.median(idf_values)

        stop_words = [word for word, idf in zip(sorted_words, sorted_idfs) if idf <= idf_threshold]
        return stop_words

# Использование классов
if __name__ == "__main__":
    preprocessor = TextPreprocessor()
    documents = [preprocessor.preprocess_text(f"{course[2]} {course[3]} {course[4]}") for course in courses]

    idf_calculator = IDFStopWords(documents)
    new_stop_words = idf_calculator.get_stop_words()
    print("Proposed new stop words:", new_stop_words)
