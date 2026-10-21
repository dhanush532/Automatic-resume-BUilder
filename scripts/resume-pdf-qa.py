"""Optional visual QA: uv run --with pymupdf python ../scripts/resume-pdf-qa.py OUTPUT.

PyMuPDF is a QA-only tool; it is not an application dependency.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend/tests")]
from resume_quality_fixture import quality_snapshot, short_snapshot  # noqa: E402

from app.services.pdf import render_pdf, render_preview_html  # noqa: E402
from app.services.resume_themes import THEMES  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--short", action="store_true")
parser.add_argument("--rail", action="store_true")
parser.add_argument("--edge", action="store_true", help="Maximum margins, monospace font, compact spacing")
args = parser.parse_args()
output = args.output
output.mkdir(parents=True, exist_ok=True)
report = {}
for key in THEMES:
    if args.rail and key != "developer":
        continue
    snapshot = short_snapshot() if args.short else quality_snapshot()
    if args.rail:
        snapshot["projects"] = []
        snapshot["education"] = [{"degree": f"QualificationMarker{i}", "institution": "Example University", "description": "Verified education detail and relevant coursework. " * 5} for i in range(25)]
    if args.edge:
        snapshot["resume_meta"]["design"] = {"margin_mm": 25, "font": "mono", "spacing": "compact", "accent": "#173c32"}
    data = render_pdf(snapshot, key)
    (output / f"{key}.pdf").write_bytes(data)
    (output / f"{key}.html").write_text(render_preview_html(snapshot, key), encoding="utf-8")
    document = fitz.open(stream=data, filetype="pdf")
    pages, outliers, overlaps = [], [], []
    text = " ".join(page.get_text() for page in document)
    for index, page in enumerate(document):
        image = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
        image.save(output / f"{key}-{index + 1}.png")
        thumbnail = Image.open(output / f"{key}-{index + 1}.png").convert("RGB")
        thumbnail.thumbnail((350, 500))
        pages.append(thumbnail)
        for word in page.get_text("words"):
            x0, y0, x1, y1 = word[:4]
            if x0 < 30 or y0 < 25 or x1 > page.rect.width - 30 or y1 > page.rect.height - 25:
                outliers.append({"page": index + 1, "word": word[4], "bbox": word[:4]})
        lines = [line for block in page.get_text("dict")["blocks"] if "lines" in block for line in block["lines"]]
        for line_index, line in enumerate(lines):
            rect = fitz.Rect(line["bbox"])
            for other in lines[line_index + 1:]:
                intersection = rect & fitz.Rect(other["bbox"])
                if intersection.width > 2 and intersection.height > 2:
                    overlaps.append({"page": index + 1, "first": line["spans"][0]["text"], "second": other["spans"][0]["text"]})
    sheet = Image.new("RGB", (360 * min(4, len(pages)), 530 * ((len(pages) + 3) // 4)), "#dfe3e0")
    draw = ImageDraw.Draw(sheet)
    for index, image in enumerate(pages):
        x, y = (index % 4) * 360 + 5, (index // 4) * 530 + 25
        sheet.paste(ImageOps.expand(image, border=1, fill="#999999"), (x, y))
        draw.text((x, y - 18), f"{key} / page {index + 1}", fill="black")
    sheet.save(output / f"{key}-all.png")
    count = 1 if args.short else 7
    markers = {f"Evidence{i}{letter}": text.count(f"Evidence{i}{letter}") for i in range(count) for letter in ("ABD" if args.short else "ABCD")} if not args.rail else {f"QualificationMarker{i}": len(re.findall(rf"\bQualificationMarker{i}\b", text)) for i in range(25)}
    report[key] = {"pages": len(document), "outliers": outliers, "overlaps": overlaps, "markers": markers, "name_count": text.count("Alex Morgan"), "links": sum(len(page.get_links()) for page in document), "blank_pages": [i + 1 for i, page in enumerate(document) if not page.get_text().strip()]}
(output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({key: {**{field: value for field, value in result.items() if field != "markers"}, "all_markers_once": all(count == 1 for count in result["markers"].values())} for key, result in report.items()}, indent=2))
if any(result["outliers"] or result["overlaps"] or result["blank_pages"] or any(count != 1 for count in result["markers"].values()) for result in report.values()):
    raise SystemExit("PDF QA found geometry or content-integrity defects; inspect report.json and rendered pages.")
