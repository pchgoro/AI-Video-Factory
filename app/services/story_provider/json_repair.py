from __future__ import annotations


def strip_simple_json_fence(text: str) -> tuple[str, list[str]]:
    stripped = text.strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        return stripped[7:-3].strip(), ["markdown_code_fence"]
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped[3:-3].strip(), ["markdown_code_fence"]
    return stripped, []
