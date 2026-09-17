"""Render a game timelapse (GIF + final PNG) from captured grid frames.

Usage: uv run python scripts/render_timelapse.py <run-dir> <out-gif>
<run-dir> holds grids.jsonl (one ownership-grid frame per decision).
"""

from __future__ import annotations

import colorsys
import json
import sys
from pathlib import Path


def decode_cells(cells: str, cols: int, rows: int) -> list[str]:
    """Expand RLE cells to a flat row-major list of class chars."""
    flat: list[str] = []
    i = 0
    while i < len(cells):
        char = cells[i]
        i += 1
        digits = ""
        while i < len(cells) and cells[i].isdigit():
            digits += cells[i]
            i += 1
        flat.extend([char] * (int(digits) if digits else 1))
    assert len(flat) == cols * rows, f"{len(flat)} != {cols * rows}"
    return flat


def palette_for(
    legend: dict[str, str], nations: list[dict]
) -> dict[str, tuple[int, int, int]]:
    """Distinct colours: water dark, land grey, human pure lime, tribes
    orange, nations spread around the hue wheel with the green band
    reserved so nothing resembles the human."""
    palette = {
        ".": (16, 32, 64),
        " ": (74, 74, 68),
        "H": (0, 255, 0),
        "T": (255, 133, 27),
    }
    nation_chars = [
        c for c, cls in legend.items() if cls not in ("water", "land", "human", "tribe")
    ]
    for i, char in enumerate(sorted(nation_chars)):
        hue = (i / max(1, len(nation_chars)) * 0.83 + 0.42) % 1.0
        r, g, b = colorsys.hls_to_rgb(hue, 0.55, 0.75)
        palette[char] = (int(r * 255), int(g * 255), int(b * 255))
    return palette


def render_frames(run_dir: Path) -> tuple[list, dict]:
    """Load frames; returns (PIL images, summary dict)."""
    from PIL import Image, ImageDraw

    frames = [
        json.loads(line)
        for line in (run_dir / "grids.jsonl").read_text().splitlines()
        if line.strip()
    ]
    if not frames:
        raise ValueError(f"no frames in {run_dir / 'grids.jsonl'}")
    first = frames[0]
    cols, rows = first["cols"], first["rows"]
    palette = palette_for(first["legend"], first["nations"])
    images = []
    for frame in frames:
        flat = decode_cells(frame["cells"], cols, rows)
        img = Image.new("RGB", (cols, rows))
        px = img.load()
        assert px is not None
        for y in range(rows):
            for x in range(cols):
                px[x, y] = palette.get(flat[y * cols + x], (255, 0, 255))
        scale = max(1, 900 // max(cols, rows))
        img = img.resize((cols * scale, rows * scale), Image.Resampling.NEAREST)
        draw = ImageDraw.Draw(img)
        draw.text(
            (6, 4),
            f"D{frame.get('decision', '?')} tick {frame['tick']}",
            fill=(255, 255, 255),
        )
        images.append(img)
    summary = {
        "frames": len(frames),
        "cols": cols,
        "rows": rows,
        "first_tick": frames[0]["tick"],
        "last_tick": frames[-1]["tick"],
    }
    return images, summary


def main() -> None:
    run_dir = Path(sys.argv[1])
    out_gif = Path(sys.argv[2])
    images, summary = render_frames(run_dir)
    images[0].save(
        out_gif,
        save_all=True,
        append_images=images[1:],
        duration=400,
        loop=0,
    )
    images[-1].save(out_gif.with_suffix(".png"))
    print(
        f"frames={summary['frames']} ticks={summary['first_tick']}->{summary['last_tick']} gif={out_gif}"
    )


if __name__ == "__main__":
    main()
