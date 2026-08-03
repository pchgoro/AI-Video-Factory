from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Story, StoryPromptRequest, StoryPromptResult


class StoryProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def build_prompt(self, request: StoryPromptRequest) -> StoryPromptResult:
        raise NotImplementedError

    @abstractmethod
    def parse_response(self, raw_response: str, project_id: str = "") -> Story:
        raise NotImplementedError
