"""Shared image-saving helpers.

Ensures rendered PNG outputs stay under a target file size by progressively
applying lossless/near-lossless size reductions before falling back to
downscaling.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

MAX_OUTPUT_BYTES = 1_000_000  # 1 MB


def save_png_under_limit(
    image: Image.Image,
    output_path: Path,
    max_bytes: int = MAX_OUTPUT_BYTES,
) -> Path:
    """Save ``image`` as a PNG at ``output_path``, staying under ``max_bytes``.

    Tries, in order:
      1. Optimized PNG at full resolution/color depth.
      2. Optimized PNG quantized to an adaptive palette (256 colors).
      3. Progressive downscaling (5% steps) of the palette version until it
         fits, or a minimum scale is reached.

    The final result (even if still over the limit) is written to disk.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def encoded_size(img: Image.Image) -> tuple[bytes, int]:
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True, compress_level=9)
        data = buf.getvalue()
        return data, len(data)

    # 1. Full quality, optimized.
    data, size = encoded_size(image)
    if size <= max_bytes:
        output_path.write_bytes(data)
        return output_path

    # 2. Adaptive palette quantization (big win for illustration/text art).
    quantized = image.convert("RGB").quantize(colors=256, method=Image.MEDIANCUT)
    data, size = encoded_size(quantized)
    if size <= max_bytes:
        output_path.write_bytes(data)
        return output_path

    # 3. Progressive downscale of the quantized image.
    base = image.convert("RGB")
    scale = 0.95
    while scale > 0.4:
        w, h = int(base.width * scale), int(base.height * scale)
        resized = base.resize((w, h), Image.LANCZOS)
        resized_q = resized.quantize(colors=256, method=Image.MEDIANCUT)
        data, size = encoded_size(resized_q)
        if size <= max_bytes:
            output_path.write_bytes(data)
            return output_path
        scale -= 0.05

    # Fall back to the smallest attempt even if still over the limit.
    output_path.write_bytes(data)
    return output_path


def save_jpeg_under_limit(
    image: Image.Image,
    output_path: Path,
    max_bytes: int = MAX_OUTPUT_BYTES,
) -> Path:
    """Save ``image`` as a JPEG at ``output_path``, staying under ``max_bytes``.

    Tries decreasing JPEG quality first, then falls back to downscaling.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base = image.convert("RGB")

    def encoded_size(img: Image.Image, quality: int) -> tuple[bytes, int]:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        return data, len(data)

    for quality in (95, 90, 85, 80, 70, 60, 50):
        data, size = encoded_size(base, quality)
        if size <= max_bytes:
            output_path.write_bytes(data)
            return output_path

    scale = 0.9
    while scale > 0.4:
        w, h = int(base.width * scale), int(base.height * scale)
        resized = base.resize((w, h), Image.LANCZOS)
        data, size = encoded_size(resized, 80)
        if size <= max_bytes:
            output_path.write_bytes(data)
            return output_path
        scale -= 0.1

    output_path.write_bytes(data)
    return output_path
