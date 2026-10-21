"""Synthetic stress document; no private career data is used in PDF QA."""
from copy import deepcopy


def quality_snapshot(long=True):
    snapshot = {
        "source": "career_passport",
        "profile": {"full_name": "Alex Morgan", "headline": "Software engineering student", "email": "alex@example.com", "location": "Berlin, Germany", "bio": "Computer science student building backend services and machine learning experiments."},
        "skills": [{"name": name, "proficiency": ""} for name in ("Python", "FastAPI", "PostgreSQL", "Docker", "PyTorch", "scikit-learn", "SQL", "React")],
        "education": [{"degree": "BSc Computer Science", "institution": "Example Technical University", "field_of_study": "Computer Science", "start_date": "2022-09-01", "is_current": True, "grade": "3.8 / 4.0", "coursework": "Algorithms, distributed systems, probability and machine learning", "achievements": "Faculty scholarship", "description": "Final-year research project in progress."}],
        "experience": [{"source_id": "exp", "title": "Software engineering intern — infrastructure and developer productivity", "company": "Example Engineering Laboratory", "start_date": "2024-06-01", "end_date": "2024-09-01", "description": "Implemented API validation for the internal service catalog.\nWrote integration tests for PostgreSQL transaction boundaries.", "achievements": "Reduced duplicated validation logic across 3 services.", "technology_notes": "Python, FastAPI, PostgreSQL, pytest, Docker"}],
        "projects": [], "professional_links": [], "certifications": [], "achievements": [], "courses": [], "languages": [], "open_source_contributions": [],
        "resume_meta": {"hidden_sections": [], "section_order": ["experience", "projects", "skills", "education"]},
    }
    for index in range(7 if long else 2):
        ml = index % 2
        snapshot["projects"].append({
            "source_id": f"project-{index}",
            "name": f"Project{index} — " + ("Reproducible machine learning experiment tracking and model evaluation workspace" if ml else "Fault-tolerant backend service orchestration and asynchronous document processing platform"),
            "description": f"Evidence{index}A: " + ("Trained PyTorch classifiers with stratified validation and documented dataset limitations." if ml else "Implemented FastAPI endpoints with PostgreSQL transactions and explicit retry handling."),
            "features": f"Evidence{index}B: " + ("Compared scikit-learn baselines with reproducible random seeds and held-out evaluation." if ml else "Added Docker development environments and SQL migration rollback checks."),
            "problem_solved": f"Evidence{index}C: Kept implementation decisions auditable through integration tests and design notes.",
            "results": f"Evidence{index}D: Ongoing work: evaluating failure recovery; production rollout is not complete.",
            "technology_notes": "Python, FastAPI, PostgreSQL, Docker, pytest, GitHub Actions, PyTorch, scikit-learn, OpenTelemetry, asynchronous task processing",
            "start_date": "2024-10-01", "is_current": True,
            "github_url": f"https://github.com/example/project-{index}/" + "long-technical-reference-" * 5,
        })
    return deepcopy(snapshot)


def short_snapshot():
    snapshot = quality_snapshot(long=False)
    snapshot["projects"] = snapshot["projects"][:1]
    snapshot["projects"][0].update(name="Project0 — Service catalog", problem_solved="", technology_notes="Python, FastAPI, PostgreSQL, Docker", github_url="https://github.com/example/catalog")
    snapshot["experience"][0].update(title="Software engineering intern", company="Example Laboratory")
    return snapshot


def imported_quality_snapshot(long=True):
    source = quality_snapshot(long) if long else short_snapshot()
    lines = ["Alex Morgan", "alex@example.com | https://github.com/example", "Summary", source["profile"]["bio"], "Projects"]
    for project in source["projects"]:
        lines.append(project["name"])
        for field in ("description", "features", "problem_solved", "results"):
            if project.get(field):
                lines.append("- " + project[field])
        lines.extend(["Technologies: " + project["technology_notes"], project["github_url"], ""])
    lines.extend(["Skills", "Python, FastAPI, PostgreSQL, Docker, PyTorch, scikit-learn", "Education", "BSc Computer Science, Example Technical University", "Verified coursework: algorithms and distributed systems."])
    return {"source": "document_import", "imported_text": "\n".join(lines)}
