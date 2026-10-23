"""Anonymized regression for the user's bullet-corrupted two-page export."""
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.services.pdf import render_pdf, resume_content
from app.services.resume_document import repair_import_lines
from app.services.resume_tailoring import tailor_snapshot
from app.services.resume_themes import THEMES

SAMPLE = """ALEX EXAMPLE
Hyderabad, India | alex@example.com |
linkedin.com/in/example

SUMMARY
Computer Science student who builds end-to-end AI products from
voice agents to full-stack web platforms.

EDUCATION
Example Technical Campus
Expected May 2028
B.Tech Computer Science | CGPA: 7.5 / 10.0

SKILLS
Languages: Python, JavaScript, TypeScript, SQL
AI / ML: LLM APIs, Whisper, ONNX

PROJECTS
• VOX — Voice-First AI Assistant with Web App Generator
• Python, FastAPI, Whisper, LLMs
• Solo project, ongoing
• Built a local voice assistant that transcribes speech, reasons with an LLM, responds with synthesized speech, and
• generates or modifies full-stack web applications from natural-language commands.
• Architected an async pipeline using CUDA-accelerated Whisper and an ONNX
• wake-word detector.
• Engineered a multi-provider gateway with failover and rate-limit
• tracking.
• Career Workspace & Application Platform
• Next.js, TypeScript, FastAPI,
• PostgreSQL, Docker
• Personal project, ongoing
• Building a full-stack career platform for centralized profiles, resume generation, job discovery, vacancy

                                                                                                        1
<PARSED TEXT FOR PAGE: 2 / 2>

• matching, and saved jobs.
• Designed a Career Passport as the single source of truth for education, projects, achievements, and
• professional links.
• FarmMarket — Market Intelligence & Policy Simulator
• Flask, SQLite, JavaScript
• Team project | 1st Place — Example Hackathon
• Built a multi-horizon predictor providing forecasts and a clear sell-now vs. store
• recommendation.
• Designed a Policy Simulator to estimate tariff effects.
• COURSEWORK & ACHIEVEMENTS
• Core subjects: Data Structures & Algorithms, DBMS, Automata Theory & Compiler Design,
OOP (Java)
• Hackathons: 1st Place — Example Hackathon; Participant — Research Challenge

                                                                                                      2
"""


def test_corrupted_export_has_three_projects_and_separate_coursework():
    content = resume_content({"source": "document_import", "imported_text": SAMPLE})
    projects = next(section for section in content["sections"] if section["key"] == "projects")
    assert len(projects["entries"]) == 3
    assert [entry["lead"] for entry in projects["entries"]] == [
        "VOX — Voice-First AI Assistant with Web App Generator",
        "Career Workspace & Application Platform",
        "FarmMarket — Market Intelligence & Policy Simulator",
    ]
    first, second, third = projects["entries"]
    assert len(first["lines"]) == 3
    assert "speech, and generates" in first["lines"][0]
    assert first["lines"][1].endswith("ONNX wake-word detector.")
    assert first["lines"][2].endswith("rate-limit tracking.")
    assert second["pre_details"] == ["Next.js, TypeScript, FastAPI, PostgreSQL, Docker", "Personal project, ongoing"]
    assert "vacancy matching, and saved jobs." in second["lines"][0]
    assert third["lines"][0].endswith("store recommendation.")
    assert any(section["label"] == "COURSEWORK & ACHIEVEMENTS" for section in content["sections"])


@pytest.mark.parametrize("key", THEMES)
def test_recovered_document_preserves_claims_and_project_headings(key):
    reader = PdfReader(BytesIO(render_pdf({"source": "document_import", "imported_text": SAMPLE}, key)))
    pages = [" ".join(page.extract_text().split()) for page in reader.pages]
    text = " ".join(pages)
    for phrase in ("rate-limit tracking.", "vacancy matching, and saved jobs.", "store recommendation.", "Personal project, ongoing", "Expected May 2028", "7.5 / 10.0", "OOP (Java)"):
        assert text.count(phrase) == 1, (key, phrase)
    assert "PARSED TEXT FOR PAGE" not in text
    for title, bullet in (("VOX", "Built a local voice assistant"), ("Career Workspace", "Building a full-stack"), ("FarmMarket", "Built a multi-horizon")):
        assert bullet in next(page for page in pages if title in page)


def test_repair_does_not_join_independent_actions_or_remove_genuine_numbers():
    text = "Projects\n• Built an API\n• Developed tests\nEducation\n2028\nSkills\nPython, SQL"
    assert "\n".join(repair_import_lines(text)) == text


def test_uppercase_indented_and_connector_wraps_join_without_changing_words():
    text = "Projects\n• Built a voice assistant using an\n    LLM, with Edge\n    Neural TTS and an ONNX\n• wake-word detector."
    assert repair_import_lines(text) == ["Projects", "• Built a voice assistant using an LLM, with Edge Neural TTS and an ONNX wake-word detector."]


def test_repaired_bulleted_project_titles_participate_in_job_tailoring():
    source = {"source": "document_import", "imported_text": SAMPLE}
    result = tailor_snapshot(source, "Frontend engineering internship", "Required: Next.js, TypeScript, PostgreSQL. Build a career workspace with profile management.")
    projects = next(section["entries"] for section in resume_content(result)["sections"] if section["key"] == "projects")
    assert projects[0]["lead"] == "Career Workspace & Application Platform"
    assert "vacancy matching, and saved jobs." in projects[0]["lines"][0]
    assert len(projects) == 3
    assert source["imported_text"] == SAMPLE
