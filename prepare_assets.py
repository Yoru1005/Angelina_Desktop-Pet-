from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "angelina_assets"
OUTPUT = ROOT / "assets"
MAX_SIZE = 380
ACTION_NAMES = ["坐坐", "拍照", "探險", "海邊", "潛水", "看書", "紙飛機", "購物", "送貨", "騎行"]


def readable_name(raw: str) -> str:
    try:
        return raw.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def remove_green(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            # The supplied animations use a vivid green-screen background.
            green_strength = g - max(r, b)
            if g > 135 and green_strength > 45:
                edge = max(0, min(255, 255 - (green_strength - 45) * 4))
                pixels[x, y] = (r, min(g, max(r, b)), b, min(a, edge))
    return rgba


def main() -> None:
    gifs = sorted((p for p in SOURCE.rglob("*.gif") if p.name != "preview.gif"), key=lambda p: p.name)
    if not gifs:
        raise SystemExit("No GIF animations found")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for index, gif_path in enumerate(gifs, start=1):
        action_id = f"action_{index:02d}"
        action_dir = OUTPUT / action_id
        action_dir.mkdir(exist_ok=True)
        frames: list[tuple[Image.Image, int]] = []
        with Image.open(gif_path) as gif:
            for frame in ImageSequence.Iterator(gif):
                duration = int(frame.info.get("duration", gif.info.get("duration", 100)))
                frames.append((remove_green(frame), max(35, duration)))

        # A common crop across all frames prevents the character from jittering.
        union = None
        for frame, _ in frames:
            bbox = frame.getchannel("A").getbbox()
            if bbox:
                mask = Image.new("1", frame.size)
                mask.paste(1, bbox)
                union = mask if union is None else ImageChops.lighter(union, mask)
        crop = union.getbbox() if union else (0, 0, frames[0][0].width, frames[0][0].height)

        durations: list[int] = []
        for frame_index, (frame, duration) in enumerate(frames):
            frame = frame.crop(crop)
            frame.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (MAX_SIZE, MAX_SIZE))
            canvas.alpha_composite(frame, ((MAX_SIZE - frame.width) // 2, MAX_SIZE - frame.height))
            canvas.save(action_dir / f"{frame_index:04d}.png", optimize=True)
            durations.append(duration)

        manifest.append({
            "id": action_id,
            "name": ACTION_NAMES[index - 1] if index <= len(ACTION_NAMES) else f"動作 {index}",
            "frames": len(frames),
            "durations": durations,
        })
        print(f"Prepared action {index}: {len(frames)} frames")

    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
