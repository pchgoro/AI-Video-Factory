from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from models import AppSettings


class SubtitleError(ValueError):
    """字幕データやASS生成に問題があるときの日本語エラーです。"""


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str


class SubtitleService:
    """ChatGPTの時間付き字幕をASS字幕ファイルへ変換します。"""

    def generate_for_project(self, project_dir: Path, settings: AppSettings) -> Path | None:
        title_text = ""
        if settings.title_enabled:
            title_file = project_dir / "title.txt"
            if not title_file.exists():
                raise SubtitleError("title.txt が見つかりません。")
            title_text = self._read_text(title_file).strip()
            if not title_text:
                raise SubtitleError("タイトルが空です。")

        subtitle_text = self._read_text(project_dir / "subtitles.txt").strip()
        cues = []
        if settings.subtitles_enabled and subtitle_text:
            cues = self.parse_subtitles(subtitle_text)

        if not settings.title_enabled and not cues:
            return None

        # Determine total duration
        total_duration = 30.0
        if cues:
            total_duration = max(cue.end for cue in cues)
        else:
            audio_file = project_dir / "audio" / "voice.wav"
            if audio_file.exists():
                try:
                    import wave
                    with wave.open(str(audio_file), "rb") as w:
                        total_duration = w.getnframes() / w.getframerate()
                except Exception:
                    pass
        if total_duration <= 0:
            total_duration = 60.0

        video_dir = project_dir / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = video_dir / "subtitles.ass"
        try:
            output_path.write_text(self.build_ass_with_title(cues, title_text, total_duration, settings), encoding="utf-8")
        except OSError as exc:
            raise SubtitleError(f"subtitles.ass の生成に失敗しました。\n{exc}") from exc
        return output_path

    def parse_subtitles(self, text: str) -> list[SubtitleCue]:
        value = text.strip()
        if not value:
            return []

        cues = []
        if value.startswith("["):
            try:
                data = json.loads(value)
            except json.JSONDecodeError as exc:
                raise SubtitleError(f"字幕JSONの形式が正しくありません。\n詳細: {exc.msg}") from exc
            cues = self._parse_json_list(data)
        else:
            cues = self._parse_arrow_lines(value)

        if not cues:
            raise SubtitleError("字幕JSONの形式が正しくありません。start / end / text を持つ配列にしてください。")

        return self._split_long_cues(cues)

    def build_ass(self, cues: list[SubtitleCue], settings: AppSettings) -> str:
        import dataclasses
        legacy_settings = dataclasses.replace(settings, title_enabled=False)
        return self.build_ass_with_title(cues, "", 0.0, legacy_settings)

    def build_ass_with_title(self, cues: list[SubtitleCue], title_text: str, total_duration: float, settings: AppSettings) -> str:
        # Subtitles settings
        alignment, margin_v = self._alignment_and_margin(settings.subtitle_position)
        shadow = 2 if settings.subtitle_shadow_enabled else 0
        font_size = max(12, int(settings.subtitle_font_size))
        outline = max(0, int(settings.subtitle_outline))

        # Title Preset Defaults
        preset = getattr(settings, "title_preset", "宇宙ドキュメンタリー風")
        
        # Design variables based on preset
        title_font = "Yu Gothic UI"
        title_color = "&H00FFFFFF"  # White
        title_outline_color = "&H00000000"  # Black
        title_border_style = 3 if settings.title_bg_enabled else 1
        title_size = settings.title_size
        title_outline = 4
        
        # Opacity calculation
        opacity = getattr(settings, "title_bg_opacity", 50)
        alpha = max(0, min(255, 255 - int(255 * opacity / 100)))
        title_back_color = f"&H{alpha:02X}000000"
        
        if preset == "シンプル":
            title_font = "Yu Gothic UI"
            title_outline = 2
        elif preset == "情報番組風":
            title_font = "Yu Gothic UI"
            title_outline = 4
        elif preset == "宇宙ドキュメンタリー風":
            title_font = "Yu Gothic UI"
            title_color = "&H00FFFFE0"  # Pale Cyan
            title_outline = 2
            title_back_color = f"&H{alpha:02X}1A0A00"  # Dark blue-black
        elif preset == "ニュース風":
            title_font = "Meiryo"
            title_outline = 4
        elif preset == "インパクト強め":
            title_font = "Meiryo"
            title_size = int(settings.title_size * 1.2)
            title_color = "&H0000FFFF"  # Yellow
            title_outline = 5
            
        # Border style is determined by title_bg_enabled checkbox
        title_border_style = 3 if settings.title_bg_enabled else 1
            
        # Apply padding (custom padding adjusts box outline size if bg is enabled)
        padding = getattr(settings, "title_padding", 15)
        if title_border_style == 3:
            title_outline = max(0, padding)
            
        # Left/Right margin based on title_width_percent
        width_percent = getattr(settings, "title_width_percent", 90)
        margin_lr = max(10, (1080 * (100 - width_percent)) // 200)

        title_align, title_margin_v = self._title_alignment_and_margin(settings.title_position)

        events = []
        if settings.title_enabled and title_text:
            title_duration_sec = self._parse_title_duration(settings.title_duration, total_duration)
            formatted_title = self._format_title_ass_text(title_text, preset, settings)
            events.append(
                f"Dialogue: 1,{self._ass_time(0.0)},{self._ass_time(title_duration_sec)},Title,,0,0,0,,{formatted_title}"
            )

        if settings.subtitles_enabled:
            for cue in cues:
                if cue.text.strip() and cue.end > cue.start:
                    events.append(
                        f"Dialogue: 0,{self._ass_time(cue.start)},{self._ass_time(cue.end)},Default,,0,0,0,,{self._ass_text(cue.text)}"
                    )

        return "\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "WrapStyle: 0",
                "ScaledBorderAndShadow: yes",
                "PlayResX: 1080",
                "PlayResY: 1920",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                f"Style: Default,Yu Gothic,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
                f"-1,0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},80,80,{margin_v},1",
                f"Style: Title,{title_font},{title_size},{title_color},&H00FFFFFF,{title_outline_color},{title_back_color},"
                f"-1,0,0,0,100,100,0,0,{title_border_style},{title_outline},0,{title_align},{margin_lr},{margin_lr},{title_margin_v},1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
                *events,
                "",
            ]
        )

    def _wrap_title(self, text: str) -> str:
        text = text.strip()
        if len(text) <= 14 or "\n" in text:
            return text

        break_chars = ["、", "，", " ", "　", ",", ".", "：", ":"]
        middle = len(text) // 2
        best_idx = -1
        min_diff = len(text)

        for i, char in enumerate(text):
            if char in break_chars:
                diff = abs(i - middle)
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i

        if best_idx != -1:
            first = text[:best_idx + 1]
            second = text[best_idx + 1:]
            if first.strip() and second.strip():
                return f"{first.strip()}\n{second.strip()}"

        first = text[:middle]
        second = text[middle:]
        return f"{first}\n{second}"

    def _format_title_ass_text(self, text: str, preset: str, settings: AppSettings) -> str:
        # 1. Wrap the title
        wrapped = self._wrap_title(text)
        
        # 2. Escape ASS special characters in user text
        escaped = wrapped.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        
        # 3. Apply keyword highlighting
        highlight_enabled = getattr(settings, "title_highlight_enabled", True)
        if highlight_enabled:
            highlight_color = "0000FFFF"  # Yellow BGR
            if preset == "宇宙ドキュメンタリー風":
                highlight_color = "0080FFFF"  # Light Orange/Yellow
            elif preset == "インパクト強め":
                highlight_color = "00FFFFFF"  # White
            
            title_size = getattr(settings, "title_size", 72)
            highlight_size = int(title_size * 1.15)
            if preset == "インパクト強め":
                highlight_size = int(title_size * 1.3)
            
            import re
            formatted = re.sub(
                r"【([\s\S]*?)】",
                rf"{{\\c&H{highlight_color}&}}{{\\fs{highlight_size}}}{{\\b1}}\1{{\\r}}",
                escaped
            )
        else:
            formatted = escaped.replace("【", "").replace("】", "")
            
        lines = [line.strip() for line in formatted.splitlines() if line.strip()]
        
        # 4. Add decoration lines if preset is "情報番組風" or "インパクト強め"
        if preset in ("情報番組風", "インパクト強め"):
            dec_line = "━━━━━━━━━━━━"
            lines.insert(0, dec_line)
            lines.append(dec_line)
            
        return r"\N".join(lines[:4])

    def _title_alignment_and_margin(self, position: str) -> tuple[int, int]:
        if "左寄せ" in position or "左" in position:
            return 7, 170
        if position == "上":
            return 8, 170
        if position == "中央":
            return 5, 0
        return 2, 170

    def _parse_title_duration(self, duration_str: str, total_duration: float) -> float:
        if "3秒" in duration_str or duration_str == "3秒" or duration_str == "3":
            return min(total_duration, 3.0)
        if "5秒" in duration_str or duration_str == "5秒" or duration_str == "5":
            return min(total_duration, 5.0)
        if "10秒" in duration_str or duration_str == "10秒" or duration_str == "10":
            return min(total_duration, 10.0)
        return total_duration

    def _parse_json_list(self, data: Any) -> list[SubtitleCue]:
        if not isinstance(data, list):
            raise SubtitleError("subtitles は配列で返してください。")

        cues: list[SubtitleCue] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                raise SubtitleError(f"字幕{index}の形式が正しくありません。start / end / text を持つオブジェクトにしてください。")
            try:
                start = float(item["start"])
                end = float(item["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise SubtitleError(f"字幕{index}の start / end は秒数の数値にしてください。") from exc
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            if end <= start:
                raise SubtitleError(f"字幕{index}の end は start より後の秒数にしてください。")
            cues.append(SubtitleCue(start=start, end=end, text=text))
        return cues

    def _parse_arrow_lines(self, text: str) -> list[SubtitleCue]:
        cues: list[SubtitleCue] = []
        pattern = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*-->\s*([0-9]+(?:\.[0-9]+)?)\s+(.+?)\s*$")
        for line in text.splitlines():
            if not line.strip():
                continue
            match = pattern.match(line)
            if not match:
                return []
            start = float(match.group(1))
            end = float(match.group(2))
            body = match.group(3).strip()
            if end <= start:
                raise SubtitleError("字幕の end は start より後の秒数にしてください。")
            cues.append(SubtitleCue(start=start, end=end, text=body))
        return cues

    def _alignment_and_margin(self, position: str) -> tuple[int, int]:
        if position == "上":
            return 8, 120
        if position == "中央":
            return 5, 0
        return 2, 160

    def _ass_time(self, seconds: float) -> str:
        centiseconds = max(0, int(round(seconds * 100)))
        cs = centiseconds % 100
        total_seconds = centiseconds // 100
        s = total_seconds % 60
        total_minutes = total_seconds // 60
        m = total_minutes % 60
        h = total_minutes // 60
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _ass_text(self, text: str) -> str:
        wrapped = self._auto_wrap_text(text)
        clean = wrapped.replace("\r\n", "\n").replace("\r", "\n")
        clean = clean.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        if not lines:
            return ""
        return r"\N".join(lines[:2])

    def _auto_wrap_text(self, text: str) -> str:
        if len(text) <= 15 or "\n" in text or "\\n" in text or "\\N" in text:
            return text

        # Find punctuation marks that can serve as break points
        break_chars = ["、", "，", " ", "　", ",", "."]
        middle = len(text) // 2
        best_idx = -1
        min_diff = len(text)

        for i, char in enumerate(text):
            if char in break_chars:
                diff = abs(i - middle)
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i

        if best_idx != -1:
            first = text[:best_idx + 1]
            second = text[best_idx + 1:]
            if first.strip() and second.strip():
                return f"{first.strip()}\n{second.strip()}"

        # If no punctuation, split at the halfway mark
        first = text[:middle]
        second = text[middle:]
        return f"{first}\n{second}"

    def _split_long_cues(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        result: list[SubtitleCue] = []
        for cue in cues:
            text = cue.text.strip()
            if len(text) <= 28:
                result.append(cue)
                continue

            split_texts = self._split_text_into_segments(text, max_len=25)
            if len(split_texts) <= 1:
                result.append(cue)
                continue

            # Distribute time proportionally
            total_chars = sum(len(t) for t in split_texts)
            if total_chars == 0:
                result.append(cue)
                continue

            duration = cue.end - cue.start
            current_start = cue.start
            for t in split_texts:
                char_len = len(t)
                part_duration = duration * (char_len / total_chars)
                part_end = current_start + part_duration
                result.append(SubtitleCue(start=round(current_start, 2), end=round(part_end, 2), text=t))
                current_start = part_end

        return result

    def _split_text_into_segments(self, text: str, max_len: int = 25) -> list[str]:
        if len(text) <= max_len:
            return [text]

        # Split by sentence endings first (。！？\n)
        sentences = re.split(r"([。！？\n])", text)
        parts = []
        current = ""
        for s in sentences:
            if not s:
                continue
            if s in "。！？\n":
                current += s
                parts.append(current)
                current = ""
            else:
                if current:
                    parts.append(current)
                    current = ""
                current = s
        if current:
            parts.append(current)

        # Split long parts by reading punctuation (、，)
        final_parts = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(part) <= max_len:
                final_parts.append(part)
            else:
                clauses = re.split(r"([、，])", part)
                sub_current = ""
                sub_parts = []
                for c in clauses:
                    if not c:
                        continue
                    if c in "、，":
                        sub_current += c
                        sub_parts.append(sub_current)
                        sub_current = ""
                    else:
                        if sub_current:
                            sub_parts.append(sub_current)
                            sub_current = ""
                        sub_current = c
                if sub_current:
                    sub_parts.append(sub_current)

                temp = ""
                for sp in sub_parts:
                    if len(temp) + len(sp) <= max_len:
                        temp += sp
                    else:
                        if temp:
                            final_parts.append(temp)
                        temp = sp
                if temp:
                    final_parts.append(temp)

        # Force split very long segments without punctuation
        very_final_parts = []
        for part in final_parts:
            part = part.strip()
            if len(part) <= 28:
                very_final_parts.append(part)
            else:
                start_idx = 0
                while start_idx < len(part):
                    very_final_parts.append(part[start_idx:start_idx+25])
                    start_idx += 25

        return very_final_parts

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""
