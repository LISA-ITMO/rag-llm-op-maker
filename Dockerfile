# Используем официальный базовый образ Python
FROM python:3.8-slim

# Установка curl для загрузки скрипта wait-for-it
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Скачивание wait-for-it.sh
RUN curl -o /wait-for-it.sh https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh \
    && chmod +x /wait-for-it.sh

# Установка зависимостей Python
COPY requirements.txt /
RUN pip install -r /requirements.txt

# Копирование файлов проекта в контейнер
COPY ./app /app

# Проверка содержимого каталога app
RUN ls -la /app

# Установка рабочей директории
WORKDIR /app

# Команда для запуска приложения с предварительной проверкой доступности Elasticsearch и PostgreSQL
CMD ["/wait-for-it.sh", "elasticsearch:9200", "--", "/wait-for-it.sh", "db:5432", "--", "python", "main.py"]
