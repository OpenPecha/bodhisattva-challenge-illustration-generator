"""Compose multi-language Bodhisattva Challenge posts.

Reads a ``day_NN_sharable_image_text.md`` file containing three language
sections (English, Tibetan, Hindi), each with a practice, verse, and verse id,
and renders one 1080x1920 image per language styled to match the branded
reference layout: a cream canvas with a thin rounded navy border, a centred
title, a bold centred challenge, a centred illustration, a left-aligned verse
with a right-aligned italic citation, and the ``@WeBuddhist`` handle.

Fonts are bundled in ``fonts/`` (Monlam Tibetan + Google Fonts).  Complex-script
shaping (Tibetan stacks, Devanagari conjuncts) requires Pillow built with
libraqm.  Verify with::

    python -c "import PIL.features as f; print(f.check('raqm'))"

Usage::

    python -m illustration_generator.compose_multilang_post <day_NN.md> <illustration_or_dir> [--output DIR]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .image_utils import save_png_under_limit

FONTS_DIR = Path(__file__).parent / "fonts"

HANDLE = "@WeBuddhist"

# Palette (approximated from the branded reference images).
COLOR_BG = "#F3EFE6"
COLOR_TITLE_EN = "#6E7EA8"
COLOR_TITLE_INDIC = "#1E2E6E"
COLOR_CHALLENGE = "#123089"
COLOR_VERSE = "#1F2D4D"
COLOR_HANDLE = "#123089"

CANVAS_SIZE = (1080, 1920)

MARGIN_X = 80
TOP_Y = 96
BOTTOM_MARGIN = 60

ILLUSTRATION_MAX_WIDTH = 940
ILLUSTRATION_MAX_HEIGHT = 760

TITLE_GAP = 54
CHALLENGE_GAP = 54
VERSE_GAP = 56
VERSE_ID_GAP = 18

SIZE_TITLE = 96
SIZE_CHALLENGE = 66
SIZE_VERSE = 46
SIZE_VERSE_ID = 40
SIZE_HANDLE = 26

# Bundled fonts.
F_LEAGUE_GOTHIC = FONTS_DIR / "LeagueGothic-VF.ttf"
F_INTER = FONTS_DIR / "Inter-VF.ttf"
F_CORMORANT = FONTS_DIR / "CormorantGaramond-VF.ttf"
F_CORMORANT_ITALIC = FONTS_DIR / "CormorantGaramond-Italic-VF.ttf"
F_MONLAM_OUCHAN5 = FONTS_DIR / "MonlamUniOuChan5.ttf"
F_MONLAM_OUCHAN4 = FONTS_DIR / "MonlamUniOuChan4.ttf"
F_MONLAM_LAKDI = FONTS_DIR / "MonlamLakdiOuchen.ttf"
F_NOTO_SERIF_DEVA = FONTS_DIR / "NotoSerifDevanagari-VF.ttf"
F_NOTO_SANS_DEVA = FONTS_DIR / "NotoSansDevanagari-VF.ttf"
F_TIRO_DEVA = FONTS_DIR / "TiroDevanagariHindi-Regular.ttf"


@dataclass
class FontSpec:
    """A font file plus optional variable-font named instance."""

    path: Path
    instance: str | None = None


@dataclass
class LangStyle:
    """Per-language title text, fonts, and colors."""

    title_template: str
    title_upper: bool
    title_color: str
    title: FontSpec
    challenge: FontSpec
    verse: FontSpec
    verse_id: FontSpec
    line_gap_ratio: float = 0.22
    verse_line_gap_ratio: float | None = None
    verse_size_scale: float = 1.0


# Per-language configuration.  Hindi challenge uses Noto Sans Devanagari Bold
# (Inter lacks Devanagari glyphs).
LANG_STYLES: dict[str, LangStyle] = {
    "english": LangStyle(
        title_template="{month_en} {day} BODHISATTVA CHALLENGE",
        title_upper=True,
        title_color=COLOR_TITLE_EN,
        title=FontSpec(F_LEAGUE_GOTHIC, "Regular"),
        challenge=FontSpec(F_INTER, "Bold"),
        verse=FontSpec(F_CORMORANT, "Medium"),
        verse_id=FontSpec(F_CORMORANT_ITALIC, "Italic"),
        line_gap_ratio=0.18,
    ),
    "tibetan": LangStyle(
        title_template="ཟླ་ {tib_month} ཚེས་ {tib_day} ཉིན་གྱི་བྱང་ཆུབ་སེམས་དཔའི་ཉམས་ལེན།",
        title_upper=False,
        title_color=COLOR_TITLE_INDIC,
        title=FontSpec(F_MONLAM_OUCHAN5),
        challenge=FontSpec(F_MONLAM_OUCHAN4),
        verse=FontSpec(F_MONLAM_LAKDI),
        verse_id=FontSpec(F_MONLAM_LAKDI),
        line_gap_ratio=0.30,
        verse_size_scale=1.35,
    ),
    "hindi": LangStyle(
        title_template="{day} {month_hi} बोधिसत्व चुनौती",
        title_upper=False,
        title_color=COLOR_TITLE_INDIC,
        title=FontSpec(F_NOTO_SERIF_DEVA, "Bold"),
        challenge=FontSpec(F_NOTO_SANS_DEVA, "Bold"),
        verse=FontSpec(F_TIRO_DEVA),
        verse_id=FontSpec(F_TIRO_DEVA),
        line_gap_ratio=0.28,
        verse_line_gap_ratio=0.55,
    ),
}


@dataclass
class LanguagePost:
    """Parsed content for a single language."""

    script: str
    practice: str
    verse: str
    verse_id: str


@dataclass
class Fonts:
    """Loaded fonts for one rendering pass."""

    title: ImageFont.FreeTypeFont
    challenge: ImageFont.FreeTypeFont
    verse: ImageFont.FreeTypeFont
    verse_id: ImageFont.FreeTypeFont
    handle: ImageFont.FreeTypeFont
    line_gap_ratio: float = 0.22
    verse_line_gap_ratio: float = 0.22


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_day_number(md_path: Path) -> int:
    """Extract the day number from a filename like ``day_20_...md``."""
    match = re.search(r"day[_-]?(\d{1,3})", md_path.name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not find a day number in filename: {md_path.name}")
    return int(match.group(1))


_MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTHS_HI = [
    "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
    "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
]
_TIB_DIGITS = str.maketrans("0123456789", "༠༡༢༣༤༥༦༧༨༩")


def _to_tibetan_digits(value: int) -> str:
    return str(value).translate(_TIB_DIGITS)


def parse_release_date(md_path: Path) -> dict[str, str]:
    """Extract the release date and return per-language title substitutions.

    Reads a line like ``**Release date:** July 25, 2026`` and returns a dict
    with keys ``month_en``, ``month_hi``, ``day``, ``tib_month``, ``tib_day``.
    """
    text = md_path.read_text(encoding="utf-8")
    match = re.search(
        r"Release date:\*\*\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text
    )
    if not match:
        raise ValueError(f"Could not find a release date in {md_path.name}")
    month_name, day = match.group(1), int(match.group(2))
    try:
        month_index = _MONTHS_EN.index(month_name.capitalize())
    except ValueError as exc:
        raise ValueError(f"Unrecognized month name: {month_name}") from exc
    return {
        "month_en": _MONTHS_EN[month_index],
        "month_hi": _MONTHS_HI[month_index],
        "day": str(day),
        "tib_month": _to_tibetan_digits(month_index + 1),
        "tib_day": _to_tibetan_digits(day),
    }


def build_title(style: LangStyle, title_parts: dict[str, str]) -> str:
    """Render a language title from its template and date substitutions."""
    title = style.title_template.format(**title_parts)
    return title.upper() if style.title_upper else title


def _detect_script(heading: str) -> str:
    lower = heading.lower()
    if lower.startswith("english"):
        return "english"
    if lower.startswith("tibetan"):
        return "tibetan"
    if lower.startswith("hindi"):
        return "hindi"
    return "unknown"


def _clean_verse_id(text: str) -> str:
    """Remove trailing Obsidian block anchors like ``(^2-15)``."""
    return re.sub(r"\s*\(\^[^)]*\)\s*$", "", text).strip()


_TIB_ORDINALS = {
    "དང་པོ": 1, "གཉིས་པ": 2, "གསུམ་པ": 3, "བཞི་པ": 4, "ལྔ་པ": 5,
    "དྲུག་པ": 6, "བདུན་པ": 7, "བརྒྱད་པ": 8, "དགུ་པ": 9, "བཅུ་པ": 10,
}


def _format_verse_id(raw: str, script: str) -> str:
    """Compact a full citation like ``Title, Chapter 2, Verse 15`` to ``Title 2:15``."""
    if script == "english":
        m = re.match(r"^(.*?),\s*Chapter\s+(\d+),\s*Verse\s+(\d+)", raw)
    elif script == "hindi":
        m = re.match(r"^(.*?),\s*अध्याय\s+([०-९]+),\s*श्लोक\s+([०-९]+)", raw)
    elif script == "tibetan":
        m = re.match(r"^(.*?)ལེའུ་([^\s།]+)།?\s*ཤློཀ་?\s*([༠-༩]+)", raw)
        if m:
            chapter_num = _TIB_ORDINALS.get(m.group(2))
            if chapter_num is None:
                return raw
            title = m.group(1).strip().rstrip("་")
            return f"{title} {_to_tibetan_digits(chapter_num)}:{m.group(3)}"
        return raw
    else:
        return raw
    if not m:
        return raw
    return f"{m.group(1).strip()} {m.group(2)}:{m.group(3)}"


def _extract_bold_blocks(section_body: str) -> list[str]:
    """Return the text values that follow each ``**label**`` in order."""
    pattern = re.compile(r"\*\*.+?\*\*\s*\n?(.*?)(?=\n\s*\*\*|\Z)", re.DOTALL)
    return [m.group(1).strip() for m in pattern.finditer(section_body)]


def parse_multilang_md(md_path: Path) -> list[LanguagePost]:
    """Parse all language sections from a sharable-image markdown file."""
    text = md_path.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^##\s+(.+?)\s*$", text)

    posts: list[LanguagePost] = []
    for i in range(1, len(parts), 2):
        heading = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        body = body.split("\n---", 1)[0]

        script = _detect_script(heading)
        if script == "unknown":
            continue

        blocks = _extract_bold_blocks(body)
        if len(blocks) < 3:
            raise ValueError(
                f"Section '{heading}' in {md_path.name} has {len(blocks)} "
                "fields, expected 3 (practice, verse, verse id)"
            )

        practice = re.sub(r"\s+", " ", blocks[0]).strip()
        verse_lines = [
            re.sub(r"[ \t]+", " ", ln).strip()
            for ln in blocks[1].splitlines()
            if ln.strip()
        ]
        verse = "\n".join(verse_lines)
        verse_id = _format_verse_id(_clean_verse_id(re.sub(r"\s+", " ", blocks[2])), script)
        posts.append(LanguagePost(script, practice, verse, verse_id))

    if not posts:
        raise ValueError(f"No recognizable language sections found in {md_path.name}")
    return posts


# --------------------------------------------------------------------------- #
# Fonts & text layout
# --------------------------------------------------------------------------- #
def _load(spec: FontSpec, size: int) -> ImageFont.FreeTypeFont:
    """Load a font (with Raqm shaping), applying a variable instance if given."""
    if not spec.path.is_file():
        raise FileNotFoundError(f"Font not found: {spec.path}")
    font = ImageFont.truetype(
        str(spec.path), size, layout_engine=ImageFont.Layout.RAQM
    )
    if spec.instance:
        try:
            font.set_variation_by_name(spec.instance)
        except OSError:
            pass
    return font


def _build_fonts(style: LangStyle, scale: float) -> Fonts:
    return Fonts(
        title=_load(style.title, int(SIZE_TITLE * scale)),
        challenge=_load(style.challenge, int(SIZE_CHALLENGE * scale)),
        verse=_load(style.verse, int(SIZE_VERSE * scale * style.verse_size_scale)),
        verse_id=_load(style.verse_id, int(SIZE_VERSE_ID * scale)),
        handle=_load(FontSpec(F_INTER, "Regular"), SIZE_HANDLE),
        line_gap_ratio=style.line_gap_ratio,
        verse_line_gap_ratio=style.verse_line_gap_ratio if style.verse_line_gap_ratio is not None else style.line_gap_ratio,
    )


def _tokenize(text: str, script: str) -> tuple[list[str], str]:
    """Split into wrap tokens. Tibetan breaks after tsheg/shad, others on space."""
    if script == "tibetan":
        tokens = re.findall(r"[^་།\s]*[་།]|\S+", text)
        return [t for t in tokens if t], ""
    return text.split(), " "


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int, script: str) -> list[str]:
    tokens, joiner = _tokenize(text, script)
    if not tokens:
        return []
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    current: list[str] = []
    for token in tokens:
        candidate = joiner.join(current + [token]) if current else token
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current.append(token)
        else:
            lines.append(joiner.join(current))
            current = [token]
    if current:
        lines.append(joiner.join(current))
    return lines


def _wrap_preserving_breaks(
    text: str, font: ImageFont.FreeTypeFont, max_width: int, script: str
) -> list[str]:
    """Wrap text line-by-line, keeping the author's original line breaks.

    Each ``\\n``-separated source line is only word-wrapped further if it
    would overflow ``max_width`` on its own.
    """
    lines: list[str] = []
    for raw_line in text.split("\n"):
        lines.extend(_wrap(raw_line, font, max_width, script))
    return lines


def _fit_verse_lines(
    post: LanguagePost, style: LangStyle, start_size: int, max_width: int, min_size: int = 22
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Shrink the verse font until every source line fits on its own row.

    Prevents a single long line from being word-wrapped into two lines while
    the rest keep their original one-line-per-line structure.
    """
    source_line_count = post.verse.count("\n") + 1
    size = start_size
    font = _load(style.verse, size)
    lines = _wrap_preserving_breaks(post.verse, font, max_width, post.script)
    while len(lines) > source_line_count and size > min_size:
        size -= 2
        font = _load(style.verse, size)
        lines = _wrap_preserving_breaks(post.verse, font, max_width, post.script)
    return font, lines


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent


def _line_advance(font: ImageFont.FreeTypeFont, gap_ratio: float) -> int:
    return int(_line_height(font) * (1.0 + gap_ratio))


def _block_height(lines: list[str], font: ImageFont.FreeTypeFont, gap_ratio: float) -> int:
    if not lines:
        return 0
    adv = _line_advance(font, gap_ratio)
    return (len(lines) - 1) * adv + _line_height(font)


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
    gap_ratio: float,
    align: str,
    left: int,
    right: int,
) -> int:
    """Draw a text block; return the y after the block. ``align`` in {left,center,right}."""
    adv = _line_advance(font, gap_ratio)
    for line in lines:
        line_w = draw.textlength(line, font=font)
        if align == "left":
            x = left
        elif align == "right":
            x = right - line_w
        else:
            x = left + (right - left - line_w) / 2
        draw.text((x, y), line, font=font, fill=fill)
        y += adv
    return y - adv + _line_height(font) if lines else y


# --------------------------------------------------------------------------- #
# Illustration
# --------------------------------------------------------------------------- #
def _prepare_illustration(path: Path, max_w: int, max_h: int) -> Image.Image:
    """Flatten onto white and scale to fit; returned as RGB for multiply blend."""
    img = Image.open(path).convert("RGBA")
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(white, img).convert("RGB")
    w, h = flat.size
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        flat = flat.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return flat


def _paste_multiply(canvas: Image.Image, illo: Image.Image, x: int, y: int) -> None:
    """Blend line-art illustration onto the cream canvas via multiply."""
    region = canvas.crop((x, y, x + illo.width, y + illo.height))
    blended = ImageChops.multiply(region, illo)
    canvas.paste(blended, (x, y))


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #
@dataclass
class Layout:
    fonts: Fonts
    title: str
    challenge_lines: list[str]
    verse_lines: list[str]
    illo: Image.Image
    total_height: int


def _measure(post: LanguagePost, style: LangStyle, title_parts: dict[str, str], illo_path: Path, scale: float) -> Layout:
    fonts = _build_fonts(style, scale)
    title = build_title(style, title_parts)

    text_width = CANVAS_SIZE[0] - 2 * MARGIN_X
    challenge_lines = _wrap(post.practice, fonts.challenge, text_width, post.script)
    fonts.verse, verse_lines = _fit_verse_lines(post, style, fonts.verse.size, text_width)

    illo = _prepare_illustration(
        illo_path,
        int(ILLUSTRATION_MAX_WIDTH * scale),
        int(ILLUSTRATION_MAX_HEIGHT * scale),
    )

    total = (
        _line_height(fonts.title)
        + TITLE_GAP
        + _block_height(challenge_lines, fonts.challenge, fonts.line_gap_ratio)
        + CHALLENGE_GAP
        + illo.height
        + VERSE_GAP
        + _block_height(verse_lines, fonts.verse, fonts.verse_line_gap_ratio)
        + VERSE_ID_GAP
        + _line_height(fonts.verse_id)
    )
    return Layout(fonts, title, challenge_lines, verse_lines, illo, total)


def compose_language_image(post: LanguagePost, title_parts: dict[str, str], illo_path: Path, output_path: Path) -> Path:
    """Render one language image to ``output_path``."""
    style = LANG_STYLES[post.script]
    width, height = CANVAS_SIZE
    top = TOP_Y
    handle_reserve = SIZE_HANDLE + 40
    available = height - top - BOTTOM_MARGIN - handle_reserve

    scale = 1.0
    layout = _measure(post, style, title_parts, illo_path, scale)
    while layout.total_height > available and scale > 0.55:
        scale -= 0.05
        layout = _measure(post, style, title_parts, illo_path, scale)

    canvas = Image.new("RGB", CANVAS_SIZE, COLOR_BG)
    draw = ImageDraw.Draw(canvas)

    fonts = layout.fonts
    left = MARGIN_X
    right = width - MARGIN_X

    # Title (fit to width).
    title_font = fonts.title
    size = title_font.size
    while draw.textlength(layout.title, font=title_font) > (right - left) and size > 40:
        size -= 2
        title_font = _load(style.title, size)
    y = top
    y = _draw_lines(
        draw, [layout.title], y=y, font=title_font, fill=style.title_color,
        gap_ratio=0, align="center", left=left, right=right,
    )
    y += TITLE_GAP

    # Challenge (centered, bold).
    y = _draw_lines(
        draw, layout.challenge_lines, y=y, font=fonts.challenge, fill=COLOR_CHALLENGE,
        gap_ratio=fonts.line_gap_ratio, align="center", left=left, right=right,
    )
    y += CHALLENGE_GAP

    # Illustration (centered, multiply blend).
    illo = layout.illo
    illo_x = (width - illo.width) // 2
    _paste_multiply(canvas, illo, illo_x, int(y))
    y += illo.height + VERSE_GAP

    # Verse (centered).
    y = _draw_lines(
        draw, layout.verse_lines, y=y, font=fonts.verse, fill=COLOR_VERSE,
        gap_ratio=fonts.verse_line_gap_ratio, align="center", left=left, right=right,
    )
    y += VERSE_ID_GAP

    # Verse id (right-aligned, italic).
    _draw_lines(
        draw, [post.verse_id], y=y, font=fonts.verse_id, fill=COLOR_VERSE,
        gap_ratio=0, align="right", left=left, right=right,
    )

    # Handle (bottom-left).
    handle_y = height - BOTTOM_MARGIN - SIZE_HANDLE
    draw.text((left, handle_y), HANDLE, font=fonts.handle, fill=COLOR_HANDLE)

    return save_png_under_limit(canvas, output_path)


def find_illustration(illustration_arg: Path, day: int) -> Path:
    """Resolve the illustration file for ``day`` (direct file or a directory)."""
    if illustration_arg.is_file():
        return illustration_arg
    if illustration_arg.is_dir():
        matches = sorted(
            p
            for p in illustration_arg.glob("*.png")
            if re.search(rf"day[_-]?0*{day}(?!\d)", p.name, re.IGNORECASE)
        )
        if not matches:
            raise FileNotFoundError(f"No illustration for day {day} in {illustration_arg}")
        return matches[0]
    raise FileNotFoundError(f"Illustration path not found: {illustration_arg}")


def save_compressed_illustration(illo_path: Path, output_dir: Path, day: int) -> Path:
    """Save a copy of the raw illustration under ``output_dir/illustration/`` under 1MB."""
    out = output_dir / "illustration" / f"day{day}.png"
    return save_png_under_limit(Image.open(illo_path), out)


def compose_all(md_path: Path, illustration_arg: Path, output_dir: Path) -> list[Path]:
    """Generate one image per language, each in its own language subfolder."""
    day = parse_day_number(md_path)
    posts = parse_multilang_md(md_path)
    title_parts = parse_release_date(md_path)
    illo_path = find_illustration(illustration_arg, day)

    outputs: list[Path] = [save_compressed_illustration(illo_path, output_dir, day)]
    for post in posts:
        out = output_dir / post.script / f"day{day}.png"
        outputs.append(compose_language_image(post, title_parts, illo_path, out))
    return outputs


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compose multi-language Bodhisattva Challenge images."
    )
    parser.add_argument("markdown", type=Path, help="day_NN_sharable_image_text.md")
    parser.add_argument(
        "illustration", type=Path, help="Illustration PNG file or a directory"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "data" / "output",
        help="Output directory (default: data/output); one subfolder per language",
    )
    args = parser.parse_args()

    try:
        outputs = compose_all(
            args.markdown.resolve(),
            args.illustration.resolve(),
            args.output.resolve(),
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    for path in outputs:
        print(f"Created: {path}")


if __name__ == "__main__":
    main()
