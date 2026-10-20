from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pypdf import PdfReader, PdfWriter

from app.schemas.resume import ResumeContentEdit
from app.services.pdf import render_pdf, render_preview_html
from app.services.resume_review import MAX_FILE_BYTES, extract_document, review_resume
from app.services.resume_snapshots import apply_content_edit

RESUME = """Alex Morgan
alex@example.com | https://github.com/alex
Summary
Software engineer focused on reliable web applications.
Experience
Built Python services for 200 users and reduced request latency by 35%.
Developed React dashboards for operations teams.
Led a team of 4 engineers through a successful launch.
Education
BSc Computer Science, Example University
Skills
Python, React, SQL, Docker
Projects
Created a job tracking application with an accessible interface.
"""


def test_checks_are_explainable_and_job_terms_use_boundaries():
    result = review_resume(RESUME, "Python, React, Kubernetes and Java. PostgreSQL required.")
    assert result["score"] == sum(check["weight"] for check in result["checks"] if check["passed"])
    assert result["job_match"]["matched"] == ["Python", "React"]
    assert "Kubernetes" in result["job_match"]["missing"]
    assert "Java" not in review_resume("JavaScript developer " * 10)["skills"]
    assert "Go" not in review_resume("I am going to manage teams " * 5)["skills"]
    assert "35%" in result["checks"][5]["evidence"][0]


def test_pdf_roundtrip_has_valid_pages_and_wrapped_content():
    text = RESUME + "\n" + "This is a long paragraph with important content. " * 150
    pdf = render_pdf({"source": "document_import", "imported_text": text}, "ats_readable")
    reader = PdfReader(BytesIO(pdf), strict=True)
    assert len(reader.pages) > 1
    assert all(page.get("/Parent") is not None for page in reader.pages)
    extracted = extract_document(pdf, "resume.pdf")
    assert "alex@example.com" in extracted
    assert " ".join(extracted.split()).count("important content") == 150


def test_docx_extraction_and_file_validation():
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + RESUME + '</w:t></w:r></w:p></w:body></w:document>')
    assert "Alex Morgan" in extract_document(stream.getvalue(), "resume.docx")
    for data, name in [(b"fake pdf", "resume.pdf"), (b"text", "resume.exe"), (b"a" * (MAX_FILE_BYTES + 1), "resume.txt"), (b"tiny", "resume.txt")]:
        with pytest.raises(ValueError):
            extract_document(data, name)


def test_html_is_escaped_and_hidden_sections_can_be_restored():
    html = render_preview_html({"source": "document_import", "imported_text": RESUME + "<script>alert(1)</script>"}, "minimal")
    assert "<script>" not in html and "&lt;script&gt;" in html
    original = {"profile": {}, "resume_meta": {"hidden_sections": ["skills"]}}
    assert apply_content_edit(original, ResumeContentEdit(hidden_sections=[]))["resume_meta"]["hidden_sections"] == []
    assert apply_content_edit(original, ResumeContentEdit())["resume_meta"]["hidden_sections"] == ["skills"]


def test_pdf_encryption_scans_and_page_limits_are_rejected():
    scanned = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(scanned)
    with pytest.raises(ValueError, match="Not enough readable text"):
        extract_document(scanned.getvalue(), "scan.pdf")
    writer.encrypt("secret")
    encrypted = BytesIO()
    writer.write(encrypted)
    with pytest.raises(ValueError, match="password"):
        extract_document(encrypted.getvalue(), "encrypted.pdf")
    writer = PdfWriter()
    for _ in range(11):
        writer.add_blank_page(width=595, height=842)
    long_pdf = BytesIO()
    writer.write(long_pdf)
    with pytest.raises(ValueError, match="10 pages"):
        extract_document(long_pdf.getvalue(), "long.pdf")


def test_export_preserves_supported_unicode():
    pdf = render_pdf({"source": "document_import", "imported_text": "Zoë García\nRésumé: improved service reliability by 25%.\nBuilt APIs."}, "minimal")
    extracted = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "Zoë García" in extracted and "Résumé" in extracted


def test_public_review_upload_export_and_auth_boundaries(client):
    response = client.post("/api/v1/review", json={"text": RESUME, "job_description": "Python and Kubernetes"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "Kubernetes" in response.json()["job_match"]["missing"]
    upload = client.post("/api/v1/review/extract", files={"file": ("resume.txt", RESUME.encode(), "text/plain")})
    assert upload.status_code == 200 and upload.json()["text"] == RESUME.strip()
    assert client.post("/api/v1/review", json={"text": "tiny"}).status_code == 422
    assert client.post("/api/v1/review", json={"text": RESUME}, headers={"Origin": "https://attacker.invalid"}).status_code == 403
    assert client.post("/api/v1/review/save", json={"text": RESUME}).status_code == 401
    exported = client.post("/api/v1/review/pdf", json={"text": RESUME})
    assert exported.status_code == 200 and len(PdfReader(BytesIO(exported.content)).pages) >= 1
    assert client.post("/api/v1/review", json={"text": " " * 90}).status_code == 422
    too_large = client.post("/api/v1/review/extract", content=b"x" * (MAX_FILE_BYTES + 65537), headers={"content-type": "application/octet-stream"})
    assert too_large.status_code == 413


def test_review_rate_limit_is_shared_and_returns_retry_after(client):
    for _ in range(30):
        assert client.post("/api/v1/review", json={"text": RESUME}).status_code == 200
    limited = client.post("/api/v1/review", json={"text": RESUME})
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3600"
