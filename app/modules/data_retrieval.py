from .rag_system import rag_system, generate_text_with_chatgpt, lemmatize_text
from .prompting import prompt_creator


def get_db_data(title, keywords, debug):
    user_query = lemmatize_text(title + ", " + keywords)
    retrieved_data = rag_system(user_query)
    result = {'user_query': user_query, 'retrieved_data': retrieved_data['text']}
    if debug:
        result['explanation'] = retrieved_data['explanation']
    return result


def do_stuff(title, keywords, level, hours, debug):
    retrieved_data = get_db_data(title, keywords, debug)
    context = f"«{retrieved_data['retrieved_data']}»" if retrieved_data['retrieved_data'] else ''
    prompt = prompt_creator(context, title, keywords, level, hours)
    generated_data = generate_text_with_chatgpt(prompt)
    result = {
        'user_query': title + ", " + keywords,
        'retrieved_data': retrieved_data['retrieved_data'],
        'generated_data': generated_data
    }
    if debug:
        result['prompt'] = prompt
        result['explanation'] = retrieved_data['explanation']
    return result
