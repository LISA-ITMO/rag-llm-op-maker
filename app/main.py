from flask import Flask, request, jsonify, render_template

from rag.rag_system import rag_system, generate_text_with_chatgpt

app = Flask(__name__)


@app.route('/generate', methods=['POST'])
def process():
    data = request.json
    text = data['text']
    result = do_stuff(text)
    return jsonify(result)


def do_stuff(user_query):
    retrieved_data = rag_system(user_query)
    prompt = (f"Based on the following course information: {retrieved_data}, generate a new course structure for "
              f"university students. Course should contain topics and subtopics")
    result = generate_text_with_chatgpt(prompt)

    data = {
        'user_query': user_query,
        'retrieved_data': retrieved_data,
        'generated_data': result
    }
    return data


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
