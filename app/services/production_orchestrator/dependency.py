from __future__ import annotations

from .models import PRODUCTION_STEPS, ProductionOptions, ProductionRun


DEPENDENCIES: dict[str, list[str]] = {
    "validate_story": [],
    "export_story": ["validate_story"],
    "generate_images": ["export_story"],
    "generate_voice": ["export_story"],
    "generate_subtitles": ["generate_voice"],
    "render_video": ["export_story", "generate_images", "generate_voice", "generate_subtitles"],
    "upload_youtube": ["render_video"],
    "upload_tiktok": ["render_video"],
}


def execution_order() -> list[str]:
    return PRODUCTION_STEPS.copy()


def dependencies_for(step_id: str) -> list[str]:
    return list(DEPENDENCIES.get(step_id, []))


def validate_no_cycles() -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            raise ValueError(f"Circular production dependency: {step_id}")
        if step_id in visited:
            return
        visiting.add(step_id)
        for dependency in dependencies_for(step_id):
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in PRODUCTION_STEPS:
        visit(step_id)


def unmet_dependencies(run: ProductionRun, step_id: str) -> list[str]:
    unmet = []
    for dependency in dependencies_for(step_id):
        step = run.step(dependency)
        if step is None:
            unmet.append(dependency)
            continue
        if step.enabled and step.status not in {"succeeded", "skipped"}:
            unmet.append(dependency)
    return unmet


def enabled_steps(options: ProductionOptions) -> list[str]:
    return [step_id for step_id in PRODUCTION_STEPS if options.is_enabled(step_id)]
