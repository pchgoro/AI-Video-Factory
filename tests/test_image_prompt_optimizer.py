from __future__ import annotations

import pytest

from services.image_generation.prompt_optimizer import PromptOptimizer


def test_optimizer_off_returns_original_prompt_exactly() -> None:
    optimizer = PromptOptimizer()

    result = optimizer.optimize("宇宙船が土星の輪を通過する", scene_index=1, max_prompt_length=2048, enabled=False)

    assert result.optimized_prompt == "宇宙船が土星の輪を通過する"
    assert result.optimizer_enabled is False
    assert result.applied_rules == []
    assert result.was_truncated is False


def test_original_prompt_over_limit_is_rejected_without_truncation() -> None:
    optimizer = PromptOptimizer()

    with pytest.raises(ValueError, match="元prompt"):
        optimizer.optimize("x" * 2049, scene_index=1, max_prompt_length=2048, enabled=True)


def test_template_is_compacted_without_changing_original_prompt() -> None:
    optimizer = PromptOptimizer()
    original = "巨大なブラックホールの降着円盤"

    result = optimizer.optimize(original, scene_index=1, max_prompt_length=len(original) + 55, enabled=True)

    assert result.original_prompt == original
    assert result.original_prompt in result.optimized_prompt
    assert result.was_compacted is True
    assert result.was_truncated is False
    assert result.removed_rules
    assert result.optimized_length <= result.max_prompt_length


def test_close_up_original_skips_wide_scene_composition() -> None:
    optimizer = PromptOptimizer()

    result = optimizer.optimize("close-up of a neutron star surface", scene_index=1, max_prompt_length=2048, enabled=True)

    assert "wide establishing" not in result.optimized_prompt
    assert any("conflicted_with_original" in item for item in result.skipped_rules)


def test_anime_style_does_not_add_realistic_rule() -> None:
    optimizer = PromptOptimizer()

    result = optimizer.optimize("anime style galaxy explorer", scene_index=2, max_prompt_length=2048, enabled=True)

    assert "realistic space documentary visual" not in result.optimized_prompt
    assert "realistic_style: conflicted_with_original" in result.skipped_rules


def test_diagram_with_labels_does_not_add_no_text() -> None:
    optimizer = PromptOptimizer()

    result = optimizer.optimize("diagram with labels explaining a black hole", scene_index=2, max_prompt_length=2048, enabled=True)

    assert "no text" not in result.optimized_prompt.lower()


def test_japanese_prompt_is_not_translated_or_rewritten() -> None:
    optimizer = PromptOptimizer()
    original = "赤い惑星が二つ並ぶ、柔らかい光"

    result = optimizer.optimize(original, scene_index=3, max_prompt_length=2048, enabled=True)

    assert result.original_prompt == original
    assert result.optimized_prompt.startswith(original)
    assert "two planets" not in result.optimized_prompt


def test_case_variant_duplicate_terms_do_not_multiply() -> None:
    optimizer = PromptOptimizer()

    result = optimizer.optimize("No Text, WITHOUT LOGO, without watermark, cinematic documentary lighting", 1, 2048, True)

    assert result.optimized_prompt.casefold().count("no text") == 1
    assert "negative_terms: already_present_or_conflicted" in result.skipped_rules
    assert "cinematic_quality: duplicate_in_original" in result.skipped_rules


def test_manifest_shape_contains_required_fields() -> None:
    optimizer = PromptOptimizer()

    result = optimizer.optimize("black hole accretion disk", 4, 2048, True)
    data = result.to_manifest()

    for key in [
        "original_prompt",
        "optimized_prompt",
        "optimizer_enabled",
        "optimizer_version",
        "scene_index",
        "scene_composition",
        "applied_rules",
        "skipped_rules",
        "removed_rules",
        "original_length",
        "optimized_length",
        "max_prompt_length",
        "was_compacted",
        "was_truncated",
    ]:
        assert key in data
