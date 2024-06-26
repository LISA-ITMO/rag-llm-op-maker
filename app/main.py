from flask import Flask, request, jsonify
import os
import json
from modules.data_retrieval import get_db_data, do_stuff

app = Flask(__name__)

@app.route('/retrieve', methods=['POST'])
def retrieve():
    data = request.json
    debug = data.get('debug', False)
    write_to_file = data.get('write_to_file', False)
    result = get_db_data(data['title'], data['keywords'], debug)

    if write_to_file:
        directory = 'retrieved'
        base_path = os.path.abspath(os.path.dirname(__file__))
        new_folder_path = os.path.join(base_path, directory)
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)
        filename = f"{data['title'].replace(' ', '_')}.json"
        full_path = os.path.join(new_folder_path, filename)
        try:
            with open(full_path, 'w') as file:
                json.dump(result['retrieved_data'], file, indent=4)
            return jsonify({
                'data': result['retrieved_data'],
                'path': full_path
            })
        except IOError as e:
            return jsonify({'error': 'Failed to write file'}), 500

    return jsonify(result)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    result = do_stuff(
        data.get('approach', 'zero-shot'),
        data['title'],
        data['keywords'],
        data.get('level', ''),
        data.get('hours', ''),
        data.get('rag', False),
        data.get('debug', False)
    )
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
