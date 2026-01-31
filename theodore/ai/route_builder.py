from sentence_transformers import SentenceTransformer
from theodore.ai.dispatch import DISPATCH
from theodore.ai.rules import IntentMetadata, RouteResult, extract_entities

def routeBuilder(text: str, intent: str, confidence_level: float):
    entities = extract_entities(text)

    route_result = RouteResult(
        intent=intent, 
        metadata=IntentMetadata(**entities), 
        confidence_level=confidence_level
        )

    return DISPATCH.dispatch_router(ctx=route_result)
