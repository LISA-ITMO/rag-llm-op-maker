class PromptBuilder:
    def __init__(self):
        self.reset()

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
        level_details = ""
        if self._level == "бакалавриат":
            level_details = "Ты разрабатываешь программу курса для студентов бакалавриата, которые впервые сталкиваются с этими темами. Сосредоточься на основных понятиях."
        elif self._level == "магистратура":
            level_details = "Ты разрабатываешь программу курса для студентов магистратуры, которые уже знакомы с базовыми аспектами и готовы к более глубокому изучению предмета."
        hours_details = f"Программа рассчитана на {self._hours} академических лекционных часов. Исходя из этого, определи оптимальное количество материала для включения в курс." if self._hours else ""

        approach_specific_prompt = self._generate_approach_specific_prompt()

        final_prompt = f"Ты помощник преподавателя. {context_prompt}Разработай структуру курса по дисциплине «{self._title}». {level_details} {hours_details} {keywords_prompt}{approach_specific_prompt}{basic_structure}"
        return final_prompt

    def _generate_approach_specific_prompt(self):
        if self._approach == 'zero-shot' or self._approach == 'few-shot':
            return ""
        elif self._approach == 'chain-of-thought':
            return (
                "Начни с анализа того, какие знания, умения и навыки у студентов уже есть до начала курса. "
                "Затем, для каждого раздела курса, объясни, почему ты выбрал именно эти темы и подтемы, "
                "и как они связаны с предыдущими знаниями студентов. "
                "Включи размышления о том, как каждая тема подготавливает студентов к последующим темам, "
                "обоснуй, почему ты считаешь, что после изучения одной темы студенты готовы перейти к следующей. "
                "Приведи примеры заданий или проектов, которые помогут закрепить полученные знания и навыки. "
                "Подведи итог, объясняя, как вся структура курса способствует достижению образовательных целей дисциплины."
            )
        elif self._approach == 'tree-of-thought':
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
        else:
            raise ValueError("Unsupported prompt type")

    def build(self):
        prompt = self.construct_prompt()
        self.reset()
        return prompt


# Пример использования:
builder = PromptBuilder()


def prompt_creator(context, title, keywords, level, hours):
    prompt = (builder.set_title(title)
              .set_approach('tree-of-thought')  # Установка другого подхода, если требуется
              .set_context(context)
              .set_keywords(keywords.split(', '))
              .set_education_level(level)
              .set_hours(hours)
              .use_rag(True)
              .build())

    return prompt
