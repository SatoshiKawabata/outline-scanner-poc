#!/usr/bin/env python3
"""Convert PDFs in test-data to JPG rasters."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fitz

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_DATA_DIR = REPO_ROOT / "test-data"


def find_pdf_jobs(data_dir: Path) -> list[tuple[Path, Path]]:
    """Return (pdf_path, raster_dir) pairs under {site}/{drawing}/original/."""
    jobs: list[tuple[Path, Path]] = []
    for original_dir in sorted(data_dir.glob("*/*/original")):
        if not original_dir.is_dir():
            continue
        raster_dir = original_dir.parent / "raster"
        for pdf_path in sorted(original_dir.glob("*.pdf")):
            jobs.append((pdf_path, raster_dir))
    return jobs


def output_filename(pdf_path: Path, page_index: int, multi_pdf: bool) -> str:
    page_num = page_index + 1
    if multi_pdf:
        return f"{pdf_path.stem}-page-{page_num:03d}.jpg"
    return f"page-{page_num:03d}.jpg"


def expected_outputs(pdf_path: Path, page_count: int, multi_pdf: bool) -> list[Path]:
    return [
        pdf_path.parent.parent / "raster" / output_filename(pdf_path, i, multi_pdf)
        for i in range(page_count)
    ]


def has_existing_outputs(output_paths: list[Path]) -> bool:
    return bool(output_paths) and all(path.exists() and path.stat().st_size > 0 for path in output_paths)


def convert_pdf(
    pdf_path: Path,
    raster_dir: Path,
    *,
    dpi: int,
    quality: int,
    force: bool,
    dry_run: bool,
    multi_pdf: bool,
) -> bool:
    label = f"{pdf_path.parent.parent.parent.name}/{pdf_path.parent.parent.name}"

    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        output_paths = expected_outputs(pdf_path, page_count, multi_pdf)

        if not force and has_existing_outputs(output_paths):
            print(f"skip: {label} ({page_count} pages already rasterized)")
            return True

        if dry_run:
            print(f"would convert: {label} ({page_count} pages) -> {raster_dir}/")
            return True

        raster_dir.mkdir(parents=True, exist_ok=True)
        matrix = fitz.Matrix(dpi / 72, dpi / 72)

        for page_index, page in enumerate(doc):
            out_path = raster_dir / output_filename(pdf_path, page_index, multi_pdf)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(str(out_path), jpg_quality=quality)
            print(
                f"{label}: page {page_index + 1}/{page_count} -> "
                f"raster/{out_path.name}"
            )

    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate JPG rasters from PDFs in test-data.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Root directory to scan (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI (default: 300)")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality 1-100 (default: 95)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if JPGs exist")
    parser.add_argument("--dry-run", action="store_true", help="List targets without converting")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = args.data_dir.resolve()

    if not data_dir.is_dir():
        print(f"error: data directory not found: {data_dir}", file=sys.stderr)
        return 1

    jobs = find_pdf_jobs(data_dir)
    if not jobs:
        print(f"error: no PDFs found under {data_dir}/*/*/original/", file=sys.stderr)
        return 1

    pdf_counts: dict[Path, int] = {}
    for pdf_path, _ in jobs:
        pdf_counts[pdf_path.parent] = pdf_counts.get(pdf_path.parent, 0) + 1

    had_error = False
    for pdf_path, raster_dir in jobs:
        multi_pdf = pdf_counts[pdf_path.parent] > 1
        try:
            convert_pdf(
                pdf_path,
                raster_dir,
                dpi=args.dpi,
                quality=args.quality,
                force=args.force,
                dry_run=args.dry_run,
                multi_pdf=multi_pdf,
            )
        except Exception as exc:
            had_error = True
            label = f"{pdf_path.parent.parent.parent.name}/{pdf_path.parent.parent.name}"
            print(f"error: {label} ({pdf_path.name}): {exc}", file=sys.stderr)

    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
