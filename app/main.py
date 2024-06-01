from flask import Flask, request, jsonify, render_template

from rag.rag_system import rag_system, generate_text_with_chatgpt

app = Flask(__name__)


@app.route('/generate', methods=['POST'])
def process():
    data = request.json
    title = data['title']
    level = data['level']
    keywords = data['keywords']
    result = do_stuff(title, keywords, level)
    return jsonify(result)


def do_stuff(title, keywords, level):
    user_query = title + " " + keywords
    retrieved_data = rag_system(user_query)
    prompt = (f"Ты помощник преподавателя. Используя имеющуюся информормацию: {retrieved_data}, разработай структуру "
              f"курса по дисциплине {title} для студентов уровня {level}"
              f"Структура должна состоять из разделов и тем. Преподаватель попросил включить следующие темы {keywords}")
    result = generate_text_with_chatgpt(prompt)

    data = {
        'user_query': user_query,
        'retrieved_data': retrieved_data['text'],
        'explanation': retrieved_data['explanation'],
        'generated_data': result
    }
    return data


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
