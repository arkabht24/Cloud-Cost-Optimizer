"""RAGAS metrics that assess retrieval quality."""


def build(evaluator_llm):
    from ragas.metrics import ContextPrecision, ContextRecall

    return [
        ContextPrecision(llm=evaluator_llm),
        ContextRecall(llm=evaluator_llm),
    ]
