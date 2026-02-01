from theodore.ai.rules import IntentMetadata, RouteResult, extract_entities
from theodore.core.lazy import get_dispatch

def routeBuilder(text: str, intent: str, confidence_level: float):
    DISPATCH = get_dispatch()
    
    entities = extract_entities(text)

    route_result = RouteResult(
        intent=intent, 
        metadata=IntentMetadata(**entities), 
        confidence_level=confidence_level
        )

    return DISPATCH.dispatch_router(ctx=route_result)
