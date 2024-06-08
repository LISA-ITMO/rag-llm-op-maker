from flask import Flask, request, jsonify, render_template
import json
import os

from rag.rag_system import rag_system, generate_text_with_chatgpt

app = Flask(__name__)


@app.route('/retrieve', methods=['POST'])
def retrieve():
    data = request.json
    title = data['title']
    keywords = data['keywords']
    debug = data.get('debug', False)
    write_to_file = data.get('write_to_file', False)

    result = get_db_data(title, keywords, debug)

    directory = 'retrieved'
    base_path = os.path.abspath(os.path.dirname(__file__))
    new_folder_path = os.path.join(base_path, directory)
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)

    if write_to_file:
        filename = f"{title.replace(' ', '_')}.json"
        full_path = os.path.join(new_folder_path, filename)
        data = result['retrieved_data']
        with open(full_path, 'w') as file:
            json.dump(data, file, indent=4)
            return jsonify(full_path)

    return jsonify(result)


@app.route('/generate', methods=['POST'])
def process():
    data = request.json
    title = data['title']
    level = data.get('level', '')
    keywords = data['keywords']
    # По дефолту будет 16 лекционных часов. Это вроде стандарт
    hours = data.get('hours', '16')
    debug = data.get('debug', False)
    result = do_stuff(title, keywords, level, hours, debug)
    return jsonify(result)


# def zero_shot():
#     return
#
# def create_prompt_using_approach(approach):
#     if approach == 'zero-shot':
#         return zero_shot()
#     if approach == 'few-shot':
#         return few_shot()
#     if approach == 'chain-of-thought':
#         return chain_of_thought()
#     if approach == 'tree-of-thought':
#         return tree_of_thought()
#     return 'Approach is not supported'


def prompt_creator(context, title, keywords, level, hours):
    auxiliary_prompt = ("Если ты разрабатываешь программу курса для студента бакалавриата, "
                        "вероятно, они будут изучать данные темы впервые. Если ты разрабатываешь программу курса "
                        "для студентов магистратуры, вероятно, они уже знакомы с азами предмета. "
                        "Немного времени нужно уделить повторению и можно углубляться в темы")
    hours_prompt = (f"Программа рассчитана на {hours} академических лекционных часов. "
                    f"Исходя из отведенного количества часов{' и уровня студентов' if level else ''}, подумай, какое "
                    f"количество материала оптимально включить в курс") if hours else ""
    level_prompt = (f"для студентов уровня {level}. ") if level else ""
    prompt = (
        f"Ты помощник преподавателя. Используя имеющуюся информормацию об имеющихся в университете курсах: {context}, разработай структуру "
        f"курса по дисциплине «{title}» {level_prompt} {hours_prompt} {auxiliary_prompt} "
        f"Преподаватель попросил включить следующие темы {keywords} "
        f"Критически важно, чтобы ответ состоял только из разделов и тем и не включать никакую дополнительную информацию, примечания и комментарии")
    return prompt


def get_db_data(title, keywords, debug):
    user_query = title + ", " + keywords
    retrieved_data = rag_system(user_query)

    data = {
        'user_query': user_query,
        'retrieved_data': retrieved_data['text'],
    }

    if debug:
        data['explanation'] = retrieved_data['explanation'],

    return data


def do_stuff(title, keywords, level, hours, debug):
    user_query = title + ", " + keywords
    retrieved_data = rag_system(user_query)
    context = f"«{retrieved_data['text']}»" if retrieved_data['text'] else ''
    prompt = prompt_creator(context, title, keywords, level, hours)
    result = generate_text_with_chatgpt(prompt)

    data = {
        'user_query': user_query,
        'retrieved_data': retrieved_data['text'],
        'generated_data': result
    }

    if debug:
        data['prompt'] = prompt
        data['explanation'] = retrieved_data['explanation'],

    return data


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
