"""RAGAS metrics that assess answer grounding, relevance, and correctness."""


def build(evaluator_llm, embeddings):
    from ragas.metrics import AnswerCorrectness, AnswerRelevancy, Faithfulness

    return [
        Faithfulness(llm=evaluator_llm),
        AnswerRelevancy(llm=evaluator_llm, embeddings=embeddings),
        AnswerCorrectness(llm=evaluator_llm, embeddings=embeddings),
    ]


def build_fast_metrics(evaluator_llm, embeddings):
    """Metrics safe to run together at the normal judge concurrency."""
    from ragas.metrics import AnswerRelevancy, Faithfulness

    return [
        Faithfulness(llm=evaluator_llm),
        AnswerRelevancy(llm=evaluator_llm, embeddings=embeddings),
    ]


def build_answer_correctness(evaluator_llm, embeddings):
    """Build correctness separately; it requires several judge calls per case."""
    from ragas.metrics import AnswerCorrectness

    return AnswerCorrectness(llm=evaluator_llm, embeddings=embeddings)


def build_faithfulness(evaluator_llm):
    from ragas.metrics import Faithfulness

    return Faithfulness(llm=evaluator_llm)


def build_answer_relevancy(evaluator_llm, embeddings):
    from ragas.metrics import AnswerRelevancy

    return AnswerRelevancy(llm=evaluator_llm, embeddings=embeddings)
