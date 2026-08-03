from .factory_adapter import FactoryExportPreview, FactoryExportResult, StoryFactoryAdapter
from .manual_prompt_provider import ManualPromptProvider
from .models import Scene, Story, StoryPromptRequest, StoryPromptResult, ValidationIssue, ValidationResult
from .validator import StoryValidationError, StoryValidator

__all__ = [
    "FactoryExportPreview",
    "FactoryExportResult",
    "ManualPromptProvider",
    "Scene",
    "Story",
    "StoryFactoryAdapter",
    "StoryPromptRequest",
    "StoryPromptResult",
    "StoryService",
    "StoryValidationError",
    "StoryValidator",
    "ValidationIssue",
    "ValidationResult",
]


def __getattr__(name: str):
    if name == "StoryService":
        from .story_service import StoryService

        return StoryService
    raise AttributeError(name)
