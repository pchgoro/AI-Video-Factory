from __future__ import annotations

from services.tag_service import TagService


def test_youtube_tags_remove_hash_and_use_commas() -> None:
    service = TagService()

    tags = service.youtube_tags_from_hashtags("#宇宙#AI\n#Shorts")

    assert tags == ["宇宙", "AI", "Shorts"]
    assert service.youtube_text(tags) == "宇宙, AI, Shorts"


def test_tiktok_tags_keep_hash_and_add_voicevox() -> None:
    service = TagService()

    tags = service.tiktok_tags_from_hashtags("#宇宙#AI")

    assert tags == ["#宇宙", "#AI", "#VOICEVOX"]
    assert service.tiktok_text(tags) == "#宇宙 #AI #VOICEVOX"


def test_tiktok_tags_do_not_duplicate_voicevox() -> None:
    service = TagService()

    tags = service.tiktok_tags_from_hashtags("#宇宙#VOICEVOX")

    assert tags == ["#宇宙", "#VOICEVOX"]
