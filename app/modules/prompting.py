import json
import os


class PromptBuilder:
    def __init__(self, examples_file=None):
        self.reset()
        self.examples = {}
        if examples_file:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            examples_file_path = os.path.join(current_dir, examples_file)
            with open(examples_file_path, 'r') as file:
                self.examples = json.load(file)

    def reset(self):
        self._title = None
        self._context = None
        self._keywords = []
        self._level = None
        self._hours = None
        self._use_rag = True
        self._approach = 'zero-shot'

    def set_title(self, title):
        self._title = title
        return self

    def set_context(self, context):
        self._context = context
        return self

    def set_keywords(self, keywords):
        if keywords:
            self._keywords = keywords
        return self

    def set_education_level(self, level):
        self._level = level
        return self

    def set_hours(self, hours):
        self._hours = hours
        return self

    def use_rag(self, use_rag):
        self._use_rag = use_rag
        return self

    def set_approach(self, approach):
        self._approach = approach
        return self

    def construct_prompt(self):
        if not self._title:
            raise ValueError("Title must be set for the prompt")

        basic_structure = "Критически важно, чтобы ответ состоял только из разделов и тем и не включать никакую дополнительную информацию, примечания и комментарии."
        context_prompt = f"Используя информацию об имеющихся в университете курсах: {self._context}, " if self._use_rag and self._context else ""
        keywords_prompt = f"Преподаватель попросил включить следующие темы: {', '.join(self._keywords)}. " if self._use_rag and self._keywords else ""

        level_details = self._generate_level_details()

        hours_details = f"Программа рассчитана на {self._hours} академических лекционных часов. Исходя из этого, определи оптимальное количество материала для включения в курс." if self._hours else ""

        approach_specific_prompt = self._generate_approach_specific_prompt()

        final_prompt = f"Ты помощник преподавателя. {context_prompt}Разработай структуру курса по дисциплине «{self._title}». {level_details} {hours_details} {keywords_prompt} {approach_specific_prompt} {basic_structure}"
        return final_prompt

    def _generate_level_details(self):
        if self._level == "бакалавриат":
            return "Ты разрабатываешь программу курса для студентов бакалавриата, которые впервые сталкиваются с этими темами. Сосредоточься на основных понятиях."
        elif self._level == "магистратура":
            return "Ты разрабатываешь программу курса для студентов магистратуры, которые уже знакомы с базовыми аспектами и готовы к более глубокому изучению предмета."
        return ""

    def _generate_approach_specific_prompt(self):
        if self._approach == 'zero-shot':
            return ''
        if self._approach == 'few-shot':
            return self._generate_few_shot_prompt()
        elif self._approach == 'chain-of-thought':
            return self._chain_of_thought()
        elif self._approach == 'tree-of-thought':
            return self._tree_of_thought()
        else:
            raise ValueError("Unsupported prompt type")

    def _tree_of_thought(self):
        return (
            "Смоделируй ситуацию, где 100 экспертов создают курс по дисциплине. Каждый эксперт включает в свой курс от 5 до 7 тем. "
            "Твоя задача — проанализировать эти программы, чтобы создать список основных тем, которые должны быть освоены. "
            "Начни с определения тем, которые встречаются как минимум в 5 программах. "
            "Рассмотри, почему эти темы часто выбираются экспертами: возможно, они являются фундаментальными "
            "или критически важными для понимания дисциплины. "
            "Затем проанализируй, как взаимосвязаны эти популярные темы и как исключение менее популярных тем может "
            "повлиять на общее понимание дисциплины. "
            "По результатам анализа, предложи итоговый список тем, объяснив, как каждая из них способствует "
            "достижению образовательных целей курса."
        )

    def _chain_of_thought(self):
        return (
            "Начни с анализа того, какие знания, умения и навыки у студентов уже есть до начала курса. "
            "Затем, для каждого раздела курса, объясни, почему ты выбрал именно эти темы и подтемы, "
            "и как они связаны с предыдущими знаниями студентов. "
            "Включи размышления о том, как каждая тема подготавливает студентов к последующим темам, "
            "обоснуй, почему ты считаешь, что после изучения одной темы студенты готовы перейти к следующей. "
            "Приведи примеры заданий или проектов, которые помогут закрепить полученные знания и навыки. "
            "Подведи итог, объясняя, как вся структура курса способствует достижению образовательных целей дисциплины."
        )

    def _generate_few_shot_prompt(self):
        if self._title in self.examples:
            examples_text = "\n\n".join([f"Пример {i + 1}:\n{example}" for i, example in enumerate(self.examples[self._title])])
            return f"Для лучшего понимания структуры, включи в запрос следующие примеры:\n{examples_text}"
        return ""

    def build(self):
        prompt = self.construct_prompt()
        self.reset()
        return prompt


# Пример использования:
builder = PromptBuilder(examples_file='../examples.json')


def prompt_creator(
        approach, context, title,
        keywords, level, hours, rag
):
    prompt = (
        builder.set_title(title)
        .set_context(context)
        .set_keywords(keywords.split(', '))
        .set_education_level(level)
        .set_hours(hours)
        .use_rag(rag)
        .set_approach(approach)
        .build())

    return prompt
