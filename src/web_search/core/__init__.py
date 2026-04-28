def __getattr__(name):
    if name == "SearchOrchestrator":
        from .orchestrator import SearchOrchestrator
        return SearchOrchestrator
    if name == "SearchOrchestratorV2":
        from .orchestrator_v2 import SearchOrchestratorV2, V2Metadata, CollisionResult
        return SearchOrchestratorV2
    if name == "V2Metadata":
        from .orchestrator_v2 import V2Metadata
        return V2Metadata
    if name == "CollisionResult":
        from .orchestrator_v2 import CollisionResult
        return CollisionResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SearchOrchestrator",
    "SearchOrchestratorV2",
    "V2Metadata",
    "CollisionResult",
]
