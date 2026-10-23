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
from resume_quality_fixture import (  # noqa: E402
    imported_quality_snapshot,
    quality_snapshot,
    short_snapshot,
)

from app.services.pdf import render_pdf, render_preview_html  # noqa: E402
from app.services.resume_tailoring import tailor_snapshot  # noqa: E402
from app.services.resume_themes import THEMES  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--short", action="store_true")
parser.add_argument("--rail", action="store_true")
parser.add_argument("--edge", action="store_true", help="Maximum margins, monospace font, compact spacing")
parser.add_argument("--imported", action="store_true", help="Exercise the imported-text theme pipeline")
parser.add_argument("--light-accent", action="store_true", help="Exercise readable foregrounds on pale custom accents")
parser.add_argument("--target", choices=("backend", "ml"), help="Generate an actual job-tailored draft before rendering")
parser.add_argument("--input-text", type=Path, help="Private supplied text; outputs should stay in an ignored directory")
args = parser.parse_args()
output = args.output
output.mkdir(parents=True, exist_ok=True)
report = {}
for key in THEMES:
    if args.rail and key != "developer":
        continue
    snapshot = short_snapshot() if args.short else quality_snapshot()
    if args.imported:
        snapshot = imported_quality_snapshot(long=not args.short)
    if args.input_text:
        snapshot = {"source": "document_import", "imported_text": args.input_text.read_text(encoding="utf-8")}
    if args.rail:
        snapshot["projects"] = []
        snapshot["education"] = [{"degree": f"QualificationMarker{i}", "institution": "Example University", "description": "Verified education detail and relevant coursework. " * 5} for i in range(25)]
    if args.edge:
        snapshot.setdefault("resume_meta", {})["design"] = {"margin_mm": 25, "font": "mono", "spacing": "compact", "accent": "#173c32"}
    if args.light_accent:
        snapshot.setdefault("resume_meta", {})["design"] = {"accent": "#ffffaa"}
    if args.target:
        title, description = (("Backend engineering internship", "Required: Python, FastAPI, PostgreSQL, Docker. Build backend services and validate retry handling.") if args.target == "backend"
                              else ("AI/ML internship", "Required: PyTorch, scikit-learn, machine learning. Train classifiers and evaluate held-out datasets."))
        snapshot = tailor_snapshot(snapshot, title, description)
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
    if args.input_text:
        from app.services.pdf import resume_content
        content = resume_content(snapshot)
        normalized_text = " ".join(text.split())
        markers = {entry["lead"]: normalized_text.count(entry["lead"]) for section in content["sections"] if section["key"] == "projects" for entry in section["entries"] if entry["lead"]}
    marker_order = list(markers)
    if args.target and not args.rail:
        marker_order = sorted(marker_order, key=lambda marker: (snapshot.get("imported_text", "").find(marker)
                              if args.imported else next(index for index, project in enumerate(snapshot["projects"]) if marker in " ".join(str(value) for value in project.values())), marker[-1]))
    marker_positions = [(" ".join(text.split()) if args.input_text else text).find(marker) for marker in marker_order]
    ordered = marker_positions == sorted(marker_positions)
    name = content["header"]["name"] if args.input_text else "Alex Morgan"
    report[key] = {"pages": len(document), "outliers": outliers, "overlaps": overlaps, "markers": markers, "reading_order": ordered,
                   "name_count": " ".join(text.split()).count(name) if name else 0, "links": sum(len(page.get_links()) for page in document), "blank_pages": [i + 1 for i, page in enumerate(document) if not page.get_text().strip()]}
(output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({key: {**{field: value for field, value in result.items() if field != "markers"}, "all_markers_once": all(count == 1 for count in result["markers"].values())} for key, result in report.items()}, indent=2))
if any(result["outliers"] or result["overlaps"] or result["blank_pages"] or not result["reading_order"] or any(count != 1 for count in result["markers"].values()) for result in report.values()):
    raise SystemExit("PDF QA found geometry or content-integrity defects; inspect report.json and rendered pages.")
