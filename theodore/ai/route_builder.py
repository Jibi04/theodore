from sentence_transformers import SentenceTransformer

from theodore.ai.intents import IntentIndex
from theodore.ai.rules import RouteResult, extract_entities, IntentMetadata, CONFIDENCE_THRESHOLD

def RouteBuilder(text: str, model: SentenceTransformer) -> None | RouteResult:
    vector = model.encode(text)

    intentCtx = IntentIndex(model=model)

    intent, confidence = intentCtx.match(vector=vector)
    if confidence < CONFIDENCE_THRESHOLD:
        return

    return RouteResult(
        intent=intent,
        confidence_level=confidence,
        metadata=compile_intent_metadata(text=text)
    )


def compile_intent_metadata(text: str) -> IntentMetadata:
    return IntentMetadata(**extract_entities(text))