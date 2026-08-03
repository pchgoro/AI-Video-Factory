from __future__ import annotations

from services.production_orchestrator.models import StepResult
from services.story_composer import StoryService

from .base import ProductionStepAdapter, StepContext


class ValidateStoryStep(ProductionStepAdapter):
    step_id = "validate_story"

    def __init__(self, story_service: StoryService) -> None:
        self.story_service = story_service

    def run(self, context: StepContext) -> StepResult:
        if self.is_cancelled(context):
            return self.cancelled()
        if context.dry_run:
            story = self.story_service.load_story(context.project)
            if story is None:
                return StepResult.failed("story.json is missing.", "missing_story", False)
            result = self.story_service.validator.validate(story)
        else:
            result = self.story_service.validate_story(context.project)
        if result.has_errors:
            return StepResult.failed("Story validation failed.", "story_validation_failed", False)
        return StepResult.succeeded(
            "Story validation succeeded.",
            {"warnings": len(result.warnings), "infos": len(result.infos)},
        )
