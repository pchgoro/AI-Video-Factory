from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .prompt_library import TemplatePromptSegments, TemplateSelectionResult


OPTIMIZER_VERSION = "1.0"


@dataclass(frozen=True)
class PromptOptimizationResult:
    original_prompt: str
    optimized_prompt: str
    optimizer_enabled: bool
    optimizer_version: str
    scene_index: int
    scene_composition: str
    applied_rules: list[str] = field(default_factory=list)
    skipped_rules: list[str] = field(default_factory=list)
    removed_rules: list[str] = field(default_factory=list)
    original_length: int = 0
    optimized_length: int = 0
    max_prompt_length: int = 2048
    was_compacted: bool = False
    was_truncated: bool = False
    selected_template: str = ""
    template_version: str = ""
    template_mode: str = "auto"
    manual_template: str | None = None
    detected_keywords: list[str] = field(default_factory=list)
    matched_sources: list[str] = field(default_factory=list)
    candidate_scores: dict[str, int] = field(default_factory=dict)
    resolution_reason: str = ""
    inherited_templates: list[str] = field(default_factory=list)
    selected_scene: str = ""
    scene_rule_applied: bool = False
    skipped_scene_reason: str | None = None
    applied_template_rules: list[str] = field(default_factory=list)
    skipped_template_rules: list[str] = field(default_factory=list)
    template_warnings: list[str] = field(default_factory=list)

    def to_manifest(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _PromptSegment:
    key: str
    text: str
    short_text: str
    priority: int


class PromptOptimizer:
    """Rule-based prompt enhancer that never rewrites the user's source prompt."""

    VERSION = OPTIMIZER_VERSION

    SCENE_COMPOSITIONS: tuple[tuple[str, str, str], ...] = (
        ("wide_establishing", "wide establishing composition with a clear cinematic focal point", "cinematic focal point"),
        ("low_angle_depth", "low-angle perspective with strong foreground depth and layered background", "foreground depth"),
        ("close_subject_detail", "intimate close subject framing with rich texture and dramatic scale", "rich subject detail"),
        ("diagonal_motion", "dynamic diagonal composition with a strong sense of motion and scale", "dynamic diagonal composition"),
        ("aerial_overview", "aerial documentary perspective showing spatial relationships and scale", "documentary aerial perspective"),
        ("side_lit_profile", "side-lit profile composition with atmospheric rim light", "side-lit composition"),
        ("deep_space_scale", "deep perspective composition with vast negative space and a distant horizon", "deep perspective scale"),
        ("immersive_point_of_view", "immersive point-of-view composition with cinematic depth cues", "immersive point of view"),
    )

    QUALITY_SEGMENTS: tuple[_PromptSegment, ...] = (
        _PromptSegment("cinematic_quality", "cinematic documentary lighting", "cinematic lighting", 10),
        _PromptSegment("high_detail", "high detail, sharp focus", "sharp focus", 20),
        _PromptSegment("consistent_mood", "consistent color grading and atmosphere", "consistent atmosphere", 30),
        _PromptSegment("production_value", "premium film still quality", "film still quality", 40),
    )
    REALISTIC_SEGMENT = _PromptSegment("realistic_style", "realistic space documentary visual", "documentary visual", 15)
    VERTICAL_SEGMENT = _PromptSegment("vertical_format", "vertical 9:16 composition for short video", "vertical composition", 20)
    NEGATIVE_SEGMENT = _PromptSegment("negative_terms", "no text, no logo, no watermark", "no logo, no watermark", 50)

    _TEXT_REQUIRED_PATTERNS = (
        "diagram",
        "label",
        "labels",
        "caption",
        "infographic",
        "chart",
        "graph",
        "text",
        "title",
        "logo",
        "??",
        "??",
        "???",
        "??",
        "??",
    )
    _NON_REALISTIC_PATTERNS = (
        "anime",
        "manga",
        "cartoon",
        "illustration",
        "watercolor",
        "oil painting",
        "sketch",
        "pixel art",
        "???",
        "??",
        "????",
        "??",
        "??",
    )
    _COMPOSITION_PATTERNS = (
        "close-up",
        "close up",
        "wide shot",
        "establishing",
        "medium shot",
        "low angle",
        "high angle",
        "aerial",
        "top-down",
        "macro",
        "first-person",
        "point of view",
        "pov",
        "???????",
        "??",
        "??",
        "??????",
        "??????",
        "???",
    )
    _NO_TEXT_EQUIVALENTS = ("no text", "without text", "textless", "????", "??????")
    _NO_LOGO_EQUIVALENTS = ("no logo", "without logo", "logo-free", "????")
    _NO_WATERMARK_EQUIVALENTS = ("no watermark", "without watermark", "watermark-free", "?????")

    def optimize(
        self,
        prompt: str,
        scene_index: int,
        max_prompt_length: int,
        enabled: bool = True,
        template_segments: TemplatePromptSegments | None = None,
        template_selection: TemplateSelectionResult | None = None,
    ) -> PromptOptimizationResult:
        original = self._cleanup_prompt(prompt)
        original_length = self._measure(original)
        if original_length > max_prompt_length:
            raise ValueError(
                f"\u5143prompt\u3060\u3051\u3067Cloudflare\u306e\u4e0a\u9650 {max_prompt_length} \u6587\u5b57\u3092\u8d85\u3048\u3066\u3044\u307e\u3059\u3002"
                "\u539f\u6587\u306f\u81ea\u52d5\u7de8\u96c6\u3057\u306a\u3044\u305f\u3081\u3001\u624b\u52d5\u3067\u77ed\u304f\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
            )
        if not enabled:
            selection_data = template_selection.to_manifest() if template_selection else {}
            return PromptOptimizationResult(
                original_prompt=original,
                optimized_prompt=original,
                optimizer_enabled=False,
                optimizer_version=self.VERSION,
                scene_index=scene_index,
                scene_composition="original",
                original_length=original_length,
                optimized_length=original_length,
                max_prompt_length=max_prompt_length,
                selected_template=str(selection_data.get("selected_template") or ""),
                template_version=str(selection_data.get("template_version") or ""),
                template_mode=str(selection_data.get("template_mode") or "auto"),
                manual_template=selection_data.get("manual_template") if isinstance(selection_data.get("manual_template"), str) else None,
                detected_keywords=list(selection_data.get("detected_keywords") or []),
                matched_sources=list(selection_data.get("matched_sources") or []),
                candidate_scores=dict(selection_data.get("candidate_scores") or {}),
                resolution_reason=str(selection_data.get("resolution_reason") or ""),
                inherited_templates=list(selection_data.get("inherited_templates") or []),
                selected_scene=str(selection_data.get("selected_scene") or ""),
                scene_rule_applied=bool(selection_data.get("scene_rule_applied") or False),
                skipped_scene_reason=selection_data.get("skipped_scene_reason") if isinstance(selection_data.get("skipped_scene_reason"), str) else None,
                template_warnings=list(selection_data.get("template_warnings") or ["optimizer disabled; template rules not applied"]),
            )

        segments, applied, skipped, scene_name = self._build_segments(original, scene_index, template_segments, template_selection)
        optimized, removed, compacted = self._compose_with_compaction(original, segments, max_prompt_length)
        optimized = self._cleanup_prompt(optimized)
        optimized_length = self._measure(optimized)
        if optimized_length > max_prompt_length:
            raise ValueError(
                f"\u6700\u9069\u5316\u5f8cprompt\u304cCloudflare\u306e\u4e0a\u9650 {max_prompt_length} \u6587\u5b57\u3092\u8d85\u3048\u3066\u3044\u307e\u3059\u3002"
                "\u54c1\u8cea\u8a9e\u53e5\u306f\u5727\u7e2e\u6e08\u307f\u3067\u3059\u304c\u53ce\u307e\u3089\u306a\u3044\u305f\u3081\u3001\u539f\u6587\u3092\u624b\u52d5\u3067\u77ed\u304f\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
            )
        selection_data = template_selection.to_manifest() if template_selection else {}
        return PromptOptimizationResult(
            original_prompt=original,
            optimized_prompt=optimized,
            optimizer_enabled=True,
            optimizer_version=self.VERSION,
            scene_index=scene_index,
            scene_composition=scene_name,
            applied_rules=applied,
            skipped_rules=skipped,
            removed_rules=removed,
            original_length=original_length,
            optimized_length=optimized_length,
            max_prompt_length=max_prompt_length,
            was_compacted=compacted,
            was_truncated=False,
            selected_template=str(selection_data.get("selected_template") or ""),
            template_version=str(selection_data.get("template_version") or ""),
            template_mode=str(selection_data.get("template_mode") or "auto"),
            manual_template=selection_data.get("manual_template") if isinstance(selection_data.get("manual_template"), str) else None,
            detected_keywords=list(selection_data.get("detected_keywords") or []),
            matched_sources=list(selection_data.get("matched_sources") or []),
            candidate_scores=dict(selection_data.get("candidate_scores") or {}),
            resolution_reason=str(selection_data.get("resolution_reason") or ""),
            inherited_templates=list(selection_data.get("inherited_templates") or []),
            selected_scene=str(selection_data.get("selected_scene") or scene_name),
            scene_rule_applied=bool(selection_data.get("scene_rule_applied") or False),
            skipped_scene_reason=selection_data.get("skipped_scene_reason") if isinstance(selection_data.get("skipped_scene_reason"), str) else None,
            applied_template_rules=list(selection_data.get("applied_template_rules") or []),
            skipped_template_rules=list(selection_data.get("skipped_template_rules") or []),
            template_warnings=list(selection_data.get("template_warnings") or []),
        )

    def _build_segments(
        self,
        original: str,
        scene_index: int,
        template_segments: TemplatePromptSegments | None = None,
        template_selection: TemplateSelectionResult | None = None,
    ) -> tuple[list[_PromptSegment], list[str], list[str], str]:
        segments: list[_PromptSegment] = []
        applied: list[str] = []
        skipped: list[str] = []

        if template_segments is not None:
            self._append_template_segments(original, template_segments, segments, applied, skipped)
        else:
            for segment in self.QUALITY_SEGMENTS:
                if self._has_equivalent(original, segment.text):
                    skipped.append(f"{segment.key}: duplicate_in_original")
                    continue
                segments.append(segment)
                applied.append(segment.key)

        if template_segments is None:
            if self._contains_any(original, self._NON_REALISTIC_PATTERNS):
                skipped.append("realistic_style: conflicted_with_original")
            elif not self._has_equivalent(original, self.REALISTIC_SEGMENT.text):
                segments.append(self.REALISTIC_SEGMENT)
                applied.append(self.REALISTIC_SEGMENT.key)

            if self._contains_aspect_hint(original):
                skipped.append("vertical_format: duplicate_or_conflicted_with_original")
            else:
                segments.append(self.VERTICAL_SEGMENT)
                applied.append(self.VERTICAL_SEGMENT.key)

        scene_name = "original"
        if self._contains_any(original, self._COMPOSITION_PATTERNS):
            skipped.append(f"scene_composition_{scene_index}: conflicted_with_original")
            if template_selection:
                template_selection.skipped_template_rules.append("scene: conflicted_with_original")
                template_selection.skipped_scene_reason = "conflicted_with_original"
        else:
            if template_segments and template_segments.scene:
                scene_name = template_selection.selected_scene if template_selection else f"scene_{scene_index}"
                scene_text = ", ".join(template_segments.scene)
                short_text = ", ".join(template_segments.scene_short or template_segments.scene[:1])
                segments.append(_PromptSegment(f"scene_composition_{scene_index}", scene_text, short_text, 25))
                applied.append(f"scene_composition_{scene_index}")
                if template_selection:
                    template_selection.scene_rule_applied = True
                    template_selection.applied_template_rules.append(f"scene.{scene_name}")
            else:
                scene_name, full_text, short_text = self.SCENE_COMPOSITIONS[(max(1, scene_index) - 1) % len(self.SCENE_COMPOSITIONS)]
                segments.append(_PromptSegment(f"scene_composition_{scene_index}", full_text, short_text, 25))
                applied.append(f"scene_composition_{scene_index}")

        if template_segments is None:
            negative = self._negative_text(original)
            if negative:
                segments.append(_PromptSegment(self.NEGATIVE_SEGMENT.key, negative, self.NEGATIVE_SEGMENT.short_text, self.NEGATIVE_SEGMENT.priority))
                applied.append(self.NEGATIVE_SEGMENT.key)
            else:
                skipped.append("negative_terms: already_present_or_conflicted")

        return segments, applied, skipped, scene_name

    def _append_template_segments(
        self,
        original: str,
        template_segments: TemplatePromptSegments,
        segments: list[_PromptSegment],
        applied: list[str],
        skipped: list[str],
    ) -> None:
        groups = [
            ("template_subject", template_segments.subject_required, 12),
            ("template_scientific_required", template_segments.scientific_required, 18),
            ("template_quality_required", template_segments.quality_required, 28),
            ("template_scientific_optional", template_segments.scientific_optional, 34),
            ("template_quality_optional", template_segments.quality_optional, 42),
        ]
        if self._contains_any(original, self._NON_REALISTIC_PATTERNS):
            skipped.append("template_realistic_style: conflicted_with_original")
        for key, values, priority in groups:
            for offset, value in enumerate(values):
                if self._has_equivalent(original, value):
                    skipped.append(f"{key}: duplicate_in_original")
                    continue
                if key.startswith("template_quality") and self._contains_any(original, self._NON_REALISTIC_PATTERNS) and "realistic" in value.casefold():
                    skipped.append(f"{key}: conflicted_with_original")
                    continue
                segments.append(_PromptSegment(f"{key}_{offset + 1}", value, value, priority))
                applied.append(f"{key}_{offset + 1}")
        negative_values = [*template_segments.negative_default, *template_segments.negative_theme_specific]
        for offset, value in enumerate(negative_values):
            if "text" in value.casefold() and self._contains_any(original, self._TEXT_REQUIRED_PATTERNS):
                skipped.append("template_negative_text: conflicted_with_original")
                continue
            if self._has_equivalent(original, value):
                skipped.append("template_negative: duplicate_in_original")
                continue
            segments.append(_PromptSegment(f"template_negative_{offset + 1}", value, value, 50))
            applied.append(f"template_negative_{offset + 1}")

    def _compose_with_compaction(
        self, original: str, segments: list[_PromptSegment], max_prompt_length: int
    ) -> tuple[str, list[str], bool]:
        removed: list[str] = []
        current = self._join(original, segments)
        if self._measure(current) <= max_prompt_length:
            return current, removed, False

        compacted = True
        deduped = self._dedupe_segments(original, segments)
        if len(deduped) != len(segments):
            removed.append("duplicate_quality_terms")
        segments = deduped
        current = self._join(original, segments)
        if self._measure(current) <= max_prompt_length:
            return current, removed, compacted

        kept = []
        for segment in segments:
            if segment.priority >= 40 and segment.key != "negative_terms":
                removed.append(segment.key)
                continue
            kept.append(segment)
        segments = kept
        current = self._join(original, segments)
        if self._measure(current) <= max_prompt_length:
            return current, removed, compacted

        shortened = []
        for segment in segments:
            if segment.key.startswith("scene_composition") and segment.short_text != segment.text:
                removed.append(f"{segment.key}: shortened")
                shortened.append(_PromptSegment(segment.key, segment.short_text, segment.short_text, segment.priority))
            else:
                shortened.append(segment)
        segments = shortened
        current = self._join(original, segments)
        if self._measure(current) <= max_prompt_length:
            return current, removed, compacted

        minimized = []
        for segment in segments:
            if segment.key == "negative_terms" and segment.short_text != segment.text:
                removed.append("negative_terms: minimized")
                minimized.append(_PromptSegment(segment.key, segment.short_text, segment.short_text, segment.priority))
            else:
                minimized.append(segment)
        segments = minimized
        current = self._cleanup_prompt(self._join(original, segments))
        if self._measure(current) <= max_prompt_length:
            return current, removed, compacted

        while segments and self._measure(current) > max_prompt_length:
            removable = max(range(len(segments)), key=lambda i: segments[i].priority)
            removed.append(segments[removable].key)
            segments.pop(removable)
            current = self._cleanup_prompt(self._join(original, segments))
        return current, removed, compacted

    def _negative_text(self, original: str) -> str:
        if self._contains_any(original, self._TEXT_REQUIRED_PATTERNS):
            parts = []
        elif self._contains_any(original, self._NO_TEXT_EQUIVALENTS):
            parts = []
        else:
            parts = ["no text"]
        if not self._contains_any(original, self._NO_LOGO_EQUIVALENTS):
            parts.append("no logo")
        if not self._contains_any(original, self._NO_WATERMARK_EQUIVALENTS):
            parts.append("no watermark")
        return ", ".join(parts)

    def _dedupe_segments(self, original: str, segments: list[_PromptSegment]) -> list[_PromptSegment]:
        seen = {self._normalize_phrase(original)}
        result = []
        for segment in segments:
            key = self._normalize_phrase(segment.text)
            if key and any(key in item or item in key for item in seen):
                continue
            seen.add(key)
            result.append(segment)
        return result

    def _join(self, original: str, segments: list[_PromptSegment]) -> str:
        additions = [segment.text for segment in segments if segment.text.strip()]
        if not additions:
            return original.strip()
        return f"{original.strip()}\n\nImage guidance: {', '.join(additions)}"

    def _has_equivalent(self, original: str, phrase: str) -> bool:
        normalized_original = self._normalize_phrase(original)
        normalized_phrase = self._normalize_phrase(phrase)
        return normalized_phrase in normalized_original

    def _contains_any(self, text: str, patterns: tuple[str, ...]) -> bool:
        lower = text.lower()
        return any(pattern.lower() in lower for pattern in patterns)

    def _contains_aspect_hint(self, text: str) -> bool:
        lower = text.lower()
        return any(value in lower for value in ("9:16", "vertical", "portrait", "縦", "縦長"))

    def _normalize_phrase(self, text: str) -> str:
        value = text.casefold()
        value = value.replace("without text", "no text")
        value = value.replace("textless", "no text")
        value = value.replace("without logo", "no logo")
        value = value.replace("logo-free", "no logo")
        value = value.replace("without watermark", "no watermark")
        value = value.replace("watermark-free", "no watermark")
        value = re.sub(r"[\s、。・,.;:!！?？/\\()\[\]{}\"'`]+", " ", value)
        return value.strip()

    def _cleanup_prompt(self, prompt: str) -> str:
        value = prompt.strip()
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        value = re.sub(r"([,、。])\1+", r"\1", value)
        return value.strip(" \t,、。")

    def _measure(self, prompt: str) -> int:
        return len(prompt)
