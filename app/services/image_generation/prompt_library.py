from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


TEMPLATE_LIBRARY_VERSION = "1.0"
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\\-]{0,63}$")


@dataclass(frozen=True)
class PromptScene:
    id: str
    camera: tuple[str, ...] = ()
    lighting: tuple[str, ...] = ()
    composition: tuple[str, ...] = ()
    short: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    name: str
    version: str
    extends: str | None = None
    priority: int = 0
    keywords: tuple[str, ...] = ()
    quality_required: tuple[str, ...] = ()
    quality_optional: tuple[str, ...] = ()
    subject_required: tuple[str, ...] = ()
    negative_default: tuple[str, ...] = ()
    negative_theme_specific: tuple[str, ...] = ()
    scientific_required: tuple[str, ...] = ()
    scientific_optional: tuple[str, ...] = ()
    scenes: tuple[PromptScene, ...] = ()
    disabled_rules: tuple[str, ...] = ()
    inherited_templates: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass
class TemplateSelectionResult:
    selected_template: str
    template_version: str
    template_mode: str
    manual_template: str | None
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
        return {
            "selected_template": self.selected_template,
            "template_version": self.template_version,
            "template_mode": self.template_mode,
            "manual_template": self.manual_template,
            "detected_keywords": self.detected_keywords,
            "matched_sources": self.matched_sources,
            "candidate_scores": self.candidate_scores,
            "resolution_reason": self.resolution_reason,
            "inherited_templates": self.inherited_templates,
            "selected_scene": self.selected_scene,
            "scene_rule_applied": self.scene_rule_applied,
            "skipped_scene_reason": self.skipped_scene_reason,
            "applied_template_rules": self.applied_template_rules,
            "skipped_template_rules": self.skipped_template_rules,
            "template_warnings": self.template_warnings,
        }


@dataclass
class TemplatePromptSegments:
    quality_required: list[str] = field(default_factory=list)
    quality_optional: list[str] = field(default_factory=list)
    subject_required: list[str] = field(default_factory=list)
    negative_default: list[str] = field(default_factory=list)
    negative_theme_specific: list[str] = field(default_factory=list)
    scientific_required: list[str] = field(default_factory=list)
    scientific_optional: list[str] = field(default_factory=list)
    scene: list[str] = field(default_factory=list)
    scene_short: list[str] = field(default_factory=list)


class PromptLibraryService:
    MAX_TEMPLATE_BYTES = 64 * 1024
    MAX_TEMPLATES = 40
    MAX_SCENES = 20
    MAX_LIST_ITEMS = 40
    MAX_STRING_LENGTH = 240
    MAX_INHERITANCE_DEPTH = 4
    SOURCE_WEIGHTS = {
        "topic": 100,
        "title": 80,
        "category": 60,
        "genre": 60,
        "series": 60,
        "tags": 50,
        "image_prompt": 20,
    }
    SUPPORTED_DISABLED_RULES = {
        "quality.required",
        "quality.optional",
        "subject.required",
        "negative.default",
        "negative.theme_specific",
        "scientific_guidance.required",
        "scientific_guidance.optional",
        "scenes",
        "scene.establishing",
        "scene.close_up",
        "scene.dynamic",
        "scene.orbital",
        "scene.ending",
    }
    DEFAULT_SCENE_ORDER = ("establishing", "close_up", "dynamic", "orbital", "ending")

    def __init__(self, library_dir: Path, logger: logging.Logger | None = None) -> None:
        self.library_dir = library_dir
        self.logger = logger or logging.getLogger("ai_video_factory.image_generation")
        self.templates: dict[str, PromptTemplate] = {}
        self.invalid_templates: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        previous = dict(self.templates)
        try:
            loaded = self._load_templates()
            resolved = self._resolve_all(loaded)
        except Exception as exc:
            self.logger.warning("template library reload failed; keeping previous library: %s", exc)
            if not self.templates:
                self.templates = {"generic_space": self._fallback_generic()}
            else:
                self.templates = previous
            return
        if "generic_space" not in resolved:
            self.logger.warning("generic_space template missing or invalid; using code fallback")
            resolved["generic_space"] = self._fallback_generic()
        self.templates = resolved
        self.logger.info("template library load complete count=%s invalid=%s", len(self.templates), len(self.invalid_templates))

    def reload(self) -> None:
        self.logger.info("template reload requested")
        self.load()

    def list_templates(self) -> list[PromptTemplate]:
        return sorted(self.templates.values(), key=lambda item: (-item.priority, item.id))

    def get_template(self, template_id: str) -> PromptTemplate:
        return self.templates.get(template_id) or self.templates.get("generic_space") or self._fallback_generic()

    def select_template(
        self,
        project,
        prompts: list[str],
        mode: str = "auto",
        manual_template: str | None = None,
    ) -> TemplateSelectionResult:
        clean_mode = "manual" if mode == "manual" else "auto"
        warnings: list[str] = []
        legacy = ""
        image_state = getattr(project, "image_generation", {}) or {}
        if isinstance(image_state, dict):
            legacy = str(image_state.get("prompt_template") or "")
        if clean_mode == "manual":
            requested = (manual_template or legacy or "generic_space").strip()
            if requested in self.templates:
                template = self.get_template(requested)
                return TemplateSelectionResult(
                    selected_template=template.id,
                    template_version=template.version,
                    template_mode="manual",
                    manual_template=requested,
                    resolution_reason="manual selection",
                    inherited_templates=list(template.inherited_templates),
                    template_warnings=list(template.warnings),
                )
            warnings.append(f"invalid manual template: {requested}")
            template = self.get_template("generic_space")
            return TemplateSelectionResult(
                selected_template=template.id,
                template_version=template.version,
                template_mode="manual",
                manual_template=requested or None,
                resolution_reason="manual selection invalid; fallback generic_space",
                inherited_templates=list(template.inherited_templates),
                template_warnings=warnings + list(template.warnings),
            )

        detection = self._detect(project, prompts)
        template = self.get_template(detection["resolved_template"])
        return TemplateSelectionResult(
            selected_template=template.id,
            template_version=template.version,
            template_mode="auto",
            manual_template=None,
            detected_keywords=detection["detected_keywords"],
            matched_sources=detection["matched_sources"],
            candidate_scores=detection["candidate_scores"],
            resolution_reason=detection["resolution_reason"],
            inherited_templates=list(template.inherited_templates),
            template_warnings=list(template.warnings),
        )

    def build_segments(self, template: PromptTemplate) -> TemplatePromptSegments:
        disabled = set(template.disabled_rules)
        return TemplatePromptSegments(
            quality_required=[] if "quality.required" in disabled else list(template.quality_required),
            quality_optional=[] if "quality.optional" in disabled else list(template.quality_optional),
            subject_required=[] if "subject.required" in disabled else list(template.subject_required),
            negative_default=[] if "negative.default" in disabled else list(template.negative_default),
            negative_theme_specific=[] if "negative.theme_specific" in disabled else list(template.negative_theme_specific),
            scientific_required=[] if "scientific_guidance.required" in disabled else list(template.scientific_required),
            scientific_optional=[] if "scientific_guidance.optional" in disabled else list(template.scientific_optional),
        )

    def scene_for_index(self, template: PromptTemplate, scene_index: int) -> PromptScene | None:
        scenes = {scene.id: scene for scene in template.scenes if f"scene.{scene.id}" not in template.disabled_rules}
        if not scenes:
            return None
        preferred = self.DEFAULT_SCENE_ORDER[(max(1, scene_index) - 1) % len(self.DEFAULT_SCENE_ORDER)]
        if preferred in scenes:
            return scenes[preferred]
        ordered = sorted(scenes.values(), key=lambda item: item.id)
        return ordered[(max(1, scene_index) - 1) % len(ordered)]

    def _load_templates(self) -> dict[str, PromptTemplate]:
        self.logger.info("template library load start path=%s", self.library_dir)
        self.invalid_templates = {}
        if not self.library_dir.exists():
            return {}
        paths = []
        for path in sorted(self.library_dir.rglob("*"), key=lambda item: str(item.relative_to(self.library_dir)).casefold()):
            if len(paths) >= self.MAX_TEMPLATES:
                self.invalid_templates[str(path)] = "template count limit exceeded"
                break
            if not path.is_file() or path.is_symlink():
                continue
            if path.name.startswith(".") or path.name.endswith((".tmp", ".bak", "~")):
                continue
            if path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            try:
                path.resolve().relative_to(self.library_dir.resolve())
            except ValueError:
                self.invalid_templates[str(path)] = "outside library"
                continue
            paths.append(path)
        templates: dict[str, PromptTemplate] = {}
        for path in paths:
            try:
                template = self._read_template(path)
            except Exception as exc:
                self.invalid_templates[str(path)] = str(exc)
                self.logger.warning("invalid template file=%s reason=%s", path.name, exc)
                continue
            if template.id in templates:
                self.invalid_templates[str(path)] = f"duplicate template id: {template.id}"
                self.logger.warning("duplicate template id=%s file=%s", template.id, path.name)
                continue
            templates[template.id] = template
        return templates

    def _read_template(self, path: Path) -> PromptTemplate:
        if path.stat().st_size > self.MAX_TEMPLATE_BYTES:
            raise ValueError("template file too large")
        text = path.read_text(encoding="utf-8")
        if "!!python" in text or "!<" in text:
            raise ValueError("unsafe yaml tag is not allowed")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid yaml: {exc}") from exc
        if not isinstance(data, dict) or not data:
            raise ValueError("empty or invalid template")
        return self._parse_template(data)

    def _parse_template(self, data: dict[str, Any]) -> PromptTemplate:
        allowed = {
            "id",
            "name",
            "version",
            "extends",
            "priority",
            "keywords",
            "quality",
            "subject",
            "negative",
            "scientific_guidance",
            "scenes",
            "disabled_rules",
        }
        warnings = [f"unknown field: {key}" for key in data if key not in allowed]
        template_id = self._required_slug(data, "id")
        name = self._required_string(data, "name")
        version = str(self._required_string(data, "version"))
        parent = data.get("extends")
        extends = None if parent in (None, "") else self._safe_slug(str(parent), "extends")
        priority = int(data.get("priority", 0) or 0)
        if priority < 0 or priority > 1000:
            raise ValueError("priority out of range")
        quality = self._mapping(data.get("quality") or {}, "quality")
        subject = self._mapping(data.get("subject") or {}, "subject")
        negative = self._mapping(data.get("negative") or {}, "negative")
        guidance = self._mapping(data.get("scientific_guidance") or {}, "scientific_guidance")
        scenes_data = data.get("scenes") or []
        disabled = tuple(self._list_of_strings(data.get("disabled_rules") or [], "disabled_rules"))
        for rule in disabled:
            if rule not in self.SUPPORTED_DISABLED_RULES and not rule.startswith("scene."):
                warnings.append(f"unknown disabled rule: {rule}")
        scenes = tuple(self._parse_scenes(scenes_data))
        return PromptTemplate(
            id=template_id,
            name=name,
            version=version,
            extends=extends,
            priority=priority,
            keywords=tuple(self._list_of_strings(data.get("keywords") or [], "keywords")),
            quality_required=tuple(self._list_of_strings((quality or {}).get("required") or [], "quality.required")),
            quality_optional=tuple(self._list_of_strings((quality or {}).get("optional") or [], "quality.optional")),
            subject_required=tuple(self._list_of_strings((subject or {}).get("required") or [], "subject.required")),
            negative_default=tuple(self._list_of_strings((negative or {}).get("default") or [], "negative.default")),
            negative_theme_specific=tuple(self._list_of_strings((negative or {}).get("theme_specific") or [], "negative.theme_specific")),
            scientific_required=tuple(self._list_of_strings((guidance or {}).get("required") or [], "scientific_guidance.required")),
            scientific_optional=tuple(self._list_of_strings((guidance or {}).get("optional") or [], "scientific_guidance.optional")),
            scenes=scenes,
            disabled_rules=disabled,
            warnings=tuple(warnings),
        )

    def _mapping(self, value: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be an object")
        return value

    def _parse_scenes(self, scenes_data: Any) -> list[PromptScene]:
        if not isinstance(scenes_data, list):
            raise ValueError("scenes must be a list")
        if len(scenes_data) > self.MAX_SCENES:
            raise ValueError("too many scenes")
        seen: set[str] = set()
        scenes: list[PromptScene] = []
        for item in scenes_data:
            if not isinstance(item, dict):
                raise ValueError("scene must be an object")
            scene_id = self._safe_slug(str(item.get("id") or ""), "scene.id")
            if scene_id in seen:
                raise ValueError(f"duplicate scene id: {scene_id}")
            seen.add(scene_id)
            scenes.append(
                PromptScene(
                    id=scene_id,
                    camera=tuple(self._list_of_strings(item.get("camera") or [], "scene.camera")),
                    lighting=tuple(self._list_of_strings(item.get("lighting") or [], "scene.lighting")),
                    composition=tuple(self._list_of_strings(item.get("composition") or [], "scene.composition")),
                    short=tuple(self._list_of_strings(item.get("short") or [], "scene.short")),
                )
            )
        return scenes

    def _resolve_all(self, templates: dict[str, PromptTemplate]) -> dict[str, PromptTemplate]:
        resolved: dict[str, PromptTemplate] = {}
        for template_id in sorted(templates):
            try:
                resolved[template_id] = self._resolve(template_id, templates, [], 0)
            except ValueError as exc:
                self.invalid_templates[template_id] = str(exc)
                self.logger.warning("inheritance error template=%s reason=%s", template_id, exc)
        return resolved

    def _resolve(
        self,
        template_id: str,
        templates: dict[str, PromptTemplate],
        stack: list[str],
        depth: int,
    ) -> PromptTemplate:
        if depth > self.MAX_INHERITANCE_DEPTH:
            raise ValueError("inheritance depth limit exceeded")
        if template_id in stack:
            raise ValueError("circular inheritance")
        template = templates.get(template_id)
        if template is None:
            raise ValueError("unknown template")
        if not template.extends:
            return copy.deepcopy(template)
        parent = templates.get(template.extends)
        if parent is None:
            raise ValueError(f"unknown parent: {template.extends}")
        resolved_parent = self._resolve(parent.id, templates, stack + [template_id], depth + 1)
        return self._merge(resolved_parent, template)

    def _merge(self, parent: PromptTemplate, child: PromptTemplate) -> PromptTemplate:
        disabled = set(parent.disabled_rules) | set(child.disabled_rules)
        scenes = {scene.id: scene for scene in parent.scenes}
        for scene in child.scenes:
            scenes[scene.id] = scene
        return PromptTemplate(
            id=child.id,
            name=child.name or parent.name,
            version=child.version or parent.version,
            extends=child.extends,
            priority=child.priority,
            keywords=tuple(self._dedupe([*parent.keywords, *child.keywords])),
            quality_required=tuple([] if "quality.required" in disabled else self._dedupe([*parent.quality_required, *child.quality_required])),
            quality_optional=tuple([] if "quality.optional" in disabled else self._dedupe([*parent.quality_optional, *child.quality_optional])),
            subject_required=tuple([] if "subject.required" in disabled else self._dedupe([*parent.subject_required, *child.subject_required])),
            negative_default=tuple([] if "negative.default" in disabled else self._dedupe([*parent.negative_default, *child.negative_default])),
            negative_theme_specific=tuple([] if "negative.theme_specific" in disabled else self._dedupe([*parent.negative_theme_specific, *child.negative_theme_specific])),
            scientific_required=tuple([] if "scientific_guidance.required" in disabled else self._dedupe([*parent.scientific_required, *child.scientific_required])),
            scientific_optional=tuple([] if "scientific_guidance.optional" in disabled else self._dedupe([*parent.scientific_optional, *child.scientific_optional])),
            scenes=tuple(scene for scene_id, scene in sorted(scenes.items()) if f"scene.{scene_id}" not in disabled and "scenes" not in disabled),
            disabled_rules=tuple(sorted(disabled)),
            inherited_templates=(*parent.inherited_templates, parent.id),
            warnings=tuple([*parent.warnings, *child.warnings]),
        )

    def _detect(self, project, prompts: list[str]) -> dict[str, Any]:
        sources = [
            ("topic", [getattr(project, "topic", "")]),
            ("title", [getattr(project, "title", "")]),
            ("category", [getattr(project, "category", "")]),
            ("genre", [getattr(project, "genre", "")]),
            ("series", [getattr(project, "series", "")]),
            ("tags", list(getattr(project, "tags", []) or [])),
            ("image_prompt", prompts[: min(3, len(prompts))]),
        ]
        scores: dict[str, int] = {}
        matched_sources: dict[str, set[str]] = {}
        detected: dict[str, set[str]] = {}
        for template in self.templates.values():
            if template.id == "generic_space":
                continue
            for source_name, values in sources:
                weight = self.SOURCE_WEIGHTS[source_name]
                haystack = " ".join(str(value) for value in values if value).casefold()
                if not haystack:
                    continue
                for keyword in template.keywords:
                    if keyword and keyword.casefold() in haystack:
                        specificity = min(len(keyword), 30)
                        scores[template.id] = scores.get(template.id, 0) + weight + specificity
                        matched_sources.setdefault(template.id, set()).add(source_name)
                        detected.setdefault(template.id, set()).add(keyword)
        if not scores:
            return {
                "resolved_template": "generic_space",
                "detected_keywords": [],
                "matched_sources": [],
                "candidate_scores": {},
                "resolution_reason": "no keyword match; fallback generic_space",
            }
        best_id = sorted(
            scores,
            key=lambda item: (-scores[item], -self.get_template(item).priority, item),
        )[0]
        return {
            "resolved_template": best_id,
            "detected_keywords": sorted(detected.get(best_id, set()), key=str.casefold),
            "matched_sources": sorted(matched_sources.get(best_id, set()), key=lambda item: list(self.SOURCE_WEIGHTS).index(item)),
            "candidate_scores": dict(sorted(scores.items())),
            "resolution_reason": "highest weighted keyword score",
        }

    def _required_slug(self, data: dict[str, Any], key: str) -> str:
        if key not in data:
            raise ValueError(f"missing required field: {key}")
        return self._safe_slug(str(data[key]), key)

    def _required_string(self, data: dict[str, Any], key: str) -> str:
        if key not in data:
            raise ValueError(f"missing required field: {key}")
        value = str(data[key]).strip()
        if not value or len(value) > self.MAX_STRING_LENGTH:
            raise ValueError(f"invalid string field: {key}")
        return value

    def _safe_slug(self, value: str, field_name: str) -> str:
        clean = value.strip()
        if not SAFE_ID_RE.fullmatch(clean):
            raise ValueError(f"invalid slug field: {field_name}")
        return clean

    def _list_of_strings(self, value: Any, field_name: str) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list")
        if len(value) > self.MAX_LIST_ITEMS:
            raise ValueError(f"{field_name} has too many items")
        result = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"{field_name} item must be a string")
            clean = item.strip()
            if not clean:
                continue
            if len(clean) > self.MAX_STRING_LENGTH:
                raise ValueError(f"{field_name} item too long")
            result.append(clean)
        return self._dedupe(result)

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _fallback_generic(self) -> PromptTemplate:
        return PromptTemplate(
            id="generic_space",
            name="Generic Space",
            version=TEMPLATE_LIBRARY_VERSION,
            priority=1,
            keywords=("space", "宇宙"),
            quality_required=("cinematic space documentary style",),
            subject_required=("clear primary subject",),
            negative_default=("no text", "no logo", "no watermark"),
            scenes=(
                PromptScene("establishing", camera=("wide establishing shot",), short=("wide shot",)),
                PromptScene("close_up", camera=("close subject detail",), short=("close detail",)),
                PromptScene("dynamic", composition=("dynamic diagonal composition",), short=("dynamic composition",)),
                PromptScene("orbital", camera=("orbital perspective",), short=("orbital view",)),
                PromptScene("ending", camera=("quiet final wide shot",), short=("final wide shot",)),
            ),
        )
