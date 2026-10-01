#!/usr/bin/env python3
"""블로그 이미지를 WebP로 변환한다.

usage:
  python to_webp.py SRC DST [--kind screenshot|illustration]

screenshot: 불필요한 알파를 제거하고, 가로 1600px을 넘으면 비율을 유지해 줄인 뒤 품질 82로 저장한다.
illustration: 투명 배경을 유지하고 무손실 WebP로 저장한다. 크기는 바꾸지 않는다.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

MAX_WIDTH = 1600


def resize_max_width(im: Image.Image, max_width: int) -> Image.Image:
    if im.width <= max_width:
        return im
    height = round(im.height * max_width / im.width)
    return im.resize((max_width, height), Image.Resampling.LANCZOS)


def convert(src: Path, dst: Path, kind: str) -> None:
    if shutil.which("cwebp") is None:
        sys.exit("cwebp가 없습니다. brew install webp")

    im = Image.open(src)
    if kind == "illustration":
        im = im.convert("RGBA")
        cwebp_args = ["-lossless", "-m", "6", "-metadata", "none"]
    else:
        im = im.convert("RGB")
        im = resize_max_width(im, MAX_WIDTH)
        cwebp_args = ["-q", "82", "-m", "6", "-metadata", "none"]

    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        prepared = Path(tmp) / "prepared.png"
        im.save(prepared, "PNG", optimize=True)
        subprocess.run(
            ["cwebp", *cwebp_args, str(prepared), "-o", str(dst)],
            check=True,
        )

    out = Image.open(dst)
    print(f"{src.name} {src.stat().st_size} -> {dst.name} {dst.stat().st_size} {out.size} {out.mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--kind", choices=("screenshot", "illustration"), default="screenshot")
    args = parser.parse_args()
    if not args.src.is_file():
        sys.exit(f"원본이 없습니다: {args.src}")
    convert(args.src, args.dst, args.kind)


if __name__ == "__main__":
    main()
