import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.routes.interviews import context_for, persist
from app.models.interview import InterviewSession
from app.schemas.interview import Evaluation, Question
from app.services import interview_ai
from app.services.pdf import render_pdf

pytest_plugins = ("tests.test_resumes",)

TEXT = "Candidate Private\ncandidate@example.com | +1 415 555 1212\nSUMMARY\nBackend engineer building Python services with PostgreSQL and FastAPI.\nPROJECTS\nEvidence API\n• Built a tested service with retry-safe asynchronous workers and PostgreSQL transactions."
EVAL = {"accuracy": 80, "relevance": 90, "clarity": 70, "feedback": "You explained retries clearly but did not cover transaction boundaries.",
        "strengths": ["Specific retry example"], "weaknesses": ["Missing transaction scope"], "corrections": ["Retries require idempotency"],
        "sample_answer": "I would use an idempotency key and an atomic transaction; the actual scale depends on the project.",
        "recommendations": ["Practice tracing a failed transaction"], "follow_up": "What if two workers process the same key?"}


@pytest.fixture
def provider(monkeypatch):
    calls = []
    def generate(schema, instruction, data):
        calls.append((schema, data))
        if schema is Evaluation:
            return Evaluation(**EVAL)
        number = data["question_number"]
        return Question(text=f"For scenario {number}, explain {['transaction isolation under concurrent writes', 'designing a durable task queue', 'testing a cache invalidation strategy'][min(number - 1, 2)]}.", category="technical")
    monkeypatch.setattr(interview_ai, "generate", generate)
    return calls


def create(client, count=3, **extra):
    response = client.post("/api/v1/interviews", json={"role": "Backend engineer", "resume_text": TEXT, "question_count": count, **extra})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def submit(client, session, answer="I use a transaction and an idempotency key to deduplicate the writes."):
    return client.post(f"/api/v1/interviews/{session['id']}/answers", json={"question_id": session["turns"][-1]["id"], "answer": answer})


def test_interview_full_persisted_lifecycle(client, resume_user, provider):
    session = create(client)
    base = f"/api/v1/interviews/{session['id']}"
    assert session["report"]["score"] is None
    assert "answer" not in session["turns"][0]
    assert client.post(base + "/next").json()["turns"] == session["turns"]
    assert submit(client, session).status_code == 200
    assert submit(client, session).status_code == 200  # Lost-response retry does not evaluate twice.
    assert len([call for call in provider if call[0] is Evaluation]) == 1
    assert submit(client, session, "Changed answer").status_code == 409
    assert client.post(base + "/control", json={"action": "pause"}).json()["status"] == "paused"
    assert client.post(base + "/next").status_code == 409
    assert client.post(base + "/control", json={"action": "resume"}).json()["status"] == "active"
    session = client.post(base + "/next").json()
    assert session["turns"][-1]["text"] != session["turns"][0]["text"]
    assert submit(client, session).status_code == 200
    session = client.post(base + "/next").json()
    assert session["turns"][-1]["difficulty"] == 3
    finished = submit(client, session).json()
    assert finished["status"] == "completed"
    assert finished["report"]["score"] == 80
    assert finished["report"]["answered"] == 3
    assert finished["report"]["recommendations"] == EVAL["recommendations"]
    assert client.get(base).json()["report"] == finished["report"]
    history = client.get("/api/v1/interviews").json()
    assert history[0]["id"] == session["id"] and "context" not in history[0] and "turns" not in history[0]
    retake = client.post(base + "/retake")
    assert retake.status_code == 201 and retake.json()["id"] != session["id"]
    assert retake.json()["report"]["answered"] == 0
    assert client.delete(base).status_code == 204
    assert client.get(base).status_code == 404


def test_all_routes_enforce_authentication(client):
    base = f"/api/v1/interviews/{uuid4()}"
    for method, path, body in [("GET", "/api/v1/interviews", None), ("GET", "/api/v1/interviews/capabilities", None),
                               ("POST", "/api/v1/interviews", {"role": "Backend engineer", "resume_text": TEXT}),
                               ("GET", base, None), ("POST", base + "/next", None), ("POST", base + "/retake", None),
                               ("POST", base + "/answers", {"question_id": str(uuid4()), "answer": "Answer"}),
                               ("POST", base + "/control", {"action": "end"}), ("DELETE", base, None)]:
        assert client.request(method, path, json=body).status_code == 401
    assert client.post("/api/v1/interviews/extract", files={"file": ("resume.pdf", b"fake", "application/pdf")}).status_code == 401


def test_other_users_cannot_read_mutate_retake_or_delete(client, db_session, resume_user, provider):
    session = create(client)
    row = db_session.get(InterviewSession, UUID(session["id"]))
    # A random non-owner UUID avoids relying on frontend-filtered lists.
    from app.api.routes.interviews import owned
    with pytest.raises(HTTPException) as exc:
        owned(db_session, uuid4(), row.id)
    assert exc.value.status_code == 404
    # Change the authenticated request to a different existing owner through the dependency boundary.
    from app.api.deps import require_authenticated_request
    from app.main import app
    app.dependency_overrides[require_authenticated_request] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid4()))
    # Rate limiting is bypassed only here: a nonexistent fake user cannot have an auth bucket.
    from app.api.routes.interviews import ai_limit
    app.dependency_overrides[ai_limit] = lambda: None
    try:
        base = f"/api/v1/interviews/{row.id}"
        for method, path, body in [("GET", base, None), ("POST", base + "/next", None), ("POST", base + "/retake", None),
                                   ("POST", base + "/answers", {"question_id": session["turns"][0]["id"], "answer": "Attempt"}),
                                   ("POST", base + "/control", {"action": "end"}), ("DELETE", base, None)]:
            assert client.request(method, path, json=body).status_code == 404
        assert client.get("/api/v1/interviews").json() == []
    finally:
        app.dependency_overrides.pop(require_authenticated_request, None)
        app.dependency_overrides.pop(ai_limit, None)


def test_expiry_pause_and_empty_report(client, db_session, resume_user, provider):
    session = create(client)
    row = db_session.get(InterviewSession, UUID(session["id"]))
    row.running_since = datetime.now(UTC) - timedelta(minutes=16)
    db_session.commit()
    assert submit(client, session).status_code == 409
    finished = client.get(f"/api/v1/interviews/{row.id}").json()
    assert finished["status"] == "completed" and finished["report"]["score"] is None
    assert client.post(f"/api/v1/interviews/{row.id}/control", json={"action": "resume"}).json()["status"] == "completed"
    session = create(client)
    base = f"/api/v1/interviews/{session['id']}"
    client.post(base + "/control", json={"action": "pause"})
    assert submit(client, session).status_code == 409
    assert client.post(base + "/control", json={"action": "end"}).json()["report"]["score"] is None


def test_provider_error_does_not_discard_progress(client, resume_user, provider, monkeypatch):
    session = create(client)
    def fail(*args):
        raise interview_ai.InterviewAIError("Quota exceeded", 429)
    monkeypatch.setattr(interview_ai, "evaluate_answer", fail)
    response = submit(client, session)
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    saved = client.get(f"/api/v1/interviews/{session['id']}").json()
    assert saved["report"]["answered"] == 0
    assert saved["turns"] == session["turns"]


def test_next_failure_keeps_already_saved_answer(client, resume_user, provider, monkeypatch):
    session = create(client)
    assert submit(client, session).status_code == 200
    def fail(*args):
        raise interview_ai.InterviewAIError("Unavailable")
    monkeypatch.setattr(interview_ai, "next_question", fail)
    assert client.post(f"/api/v1/interviews/{session['id']}/next").status_code == 503
    saved = client.get(f"/api/v1/interviews/{session['id']}").json()
    assert saved["report"]["answered"] == 1 and saved["turns"][0]["answer"]


def test_optimistic_revision_rejects_stale_writes(client, db_session, resume_user, provider):
    session = create(client)
    row = db_session.get(InterviewSession, UUID(session["id"]))
    from sqlalchemy import update
    db_session.execute(update(InterviewSession).where(InterviewSession.id == row.id).values(revision=2).execution_options(synchronize_session=False))
    with pytest.raises(HTTPException) as exc:
        persist(db_session, row, status="completed")
    assert exc.value.status_code == 409


def test_saved_resume_source_and_authorization(client, resume_user, provider):
    saved = client.post("/api/v1/review/save", json={"text": TEXT, "name": "Practice resume"}).json()
    response = client.post("/api/v1/interviews", json={"role": "Engineer", "resume_id": saved["id"]})
    assert response.status_code == 201
    assert response.json()["resume_id"] == saved["id"]
    assert client.post("/api/v1/interviews", json={"role": "Engineer", "resume_id": str(uuid4())}).status_code == 404
    assert client.post("/api/v1/interviews", json={"role": "Engineer", "resume_id": saved["id"], "resume_text": TEXT}).status_code == 422


def test_pdf_extract_and_context_redaction(client, resume_user):
    pdf = render_pdf({"source": "document_import", "imported_text": TEXT}, "ats_readable")
    response = client.post("/api/v1/interviews/extract", files={"file": ("resume.pdf", BytesIO(pdf), "application/pdf")})
    assert response.status_code == 200 and "PostgreSQL" in response.json()["text"]
    assert client.post("/api/v1/interviews/extract", files={"file": ("wrong.pdf", b"not pdf", "application/pdf")}).status_code == 422
    context = context_for({"source": "document_import", "imported_text": TEXT})
    assert "Candidate Private" not in context and "candidate@example.com" not in context
    assert "415 555" not in context and "transactions" in context


def test_missing_key_cannot_create_fake_session(client, db_session, resume_user, monkeypatch):
    monkeypatch.setattr(interview_ai, "get_settings", lambda: SimpleNamespace(gemini_api_key=None))
    before = db_session.scalar(select(func.count()).select_from(InterviewSession))
    response = client.post("/api/v1/interviews", json={"role": "Engineer", "resume_text": TEXT})
    assert response.status_code == 503 and "not configured" in response.text
    assert db_session.scalar(select(func.count()).select_from(InterviewSession)) == before


@pytest.mark.parametrize("body", [{"role": " "}, {"role": "Engineer", "resume_text": TEXT, "question_count": 21},
                                 {"role": "Engineer", "resume_text": TEXT, "duration_minutes": 0},
                                 {"role": "Engineer", "resume_text": TEXT, "interview_type": "unknown"}])
def test_invalid_configuration(client, resume_user, body):
    assert client.post("/api/v1/interviews", json=body).status_code == 422


def mock_http(monkeypatch, status=200, payload=None):
    captured = []
    original = httpx.Client
    def handler(request):
        captured.append(request)
        return httpx.Response(status, json=payload)
    monkeypatch.setattr(interview_ai, "get_settings", lambda: SimpleNamespace(gemini_api_key="test-not-a-secret", gemini_interview_model="gemini-3.8-flash"))
    monkeypatch.setattr(interview_ai.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return captured


def test_real_provider_boundary_builds_valid_rest_request(monkeypatch):
    captured = mock_http(monkeypatch, payload={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(EVAL)}]}}]})
    result = interview_ai.generate(Evaluation, "Evaluate", {"answer": "A real answer"})
    assert result.accuracy == 80
    request = captured[0]
    assert request.headers["x-goog-api-key"] == "test-not-a-secret"
    assert "test-not-a-secret" not in str(request.url)
    body = json.loads(request.content)
    assert body["generationConfig"]["responseJsonSchema"]["properties"]["accuracy"]["maximum"] == 100


@pytest.mark.parametrize(("status", "payload", "expected"), [(429, {}, 429), (403, {}, 503), (500, {}, 503),
    (200, [], 502), (200, {"candidates": []}, 502), (200, {"candidates": [{"finishReason": "MAX_TOKENS"}]}, 502),
    (200, {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not JSON"}]}}]}, 502),
    (200, {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({**EVAL, "accuracy": 101})}]}}]}, 502)])
def test_provider_failures_are_safe(monkeypatch, status, payload, expected):
    mock_http(monkeypatch, status, payload)
    with pytest.raises(interview_ai.InterviewAIError) as exc:
        interview_ai.generate(Evaluation, "Evaluate", {})
    assert exc.value.status == expected and "test-not-a-secret" not in str(exc.value)


def test_repeated_questions_are_rejected(monkeypatch):
    question = "Explain transaction isolation under concurrent database writes."
    monkeypatch.setattr(interview_ai, "generate", lambda *args: Question(text=question, category="technical"))
    session = SimpleNamespace(turns=[{"text": question}], difficulty=2, role="Engineer", job_description="", context="Career evidence", interview_type="technical")
    with pytest.raises(interview_ai.InterviewAIError):
        interview_ai.next_question(session)


def test_adaptation_uses_recent_evaluations_and_followup(monkeypatch):
    captured = []
    monkeypatch.setattr(interview_ai, "generate", lambda schema, instruction, data: captured.append(data) or Question(text="How would you recover lost task acknowledgements?", category="technical"))
    session = SimpleNamespace(turns=[{"text": f"Question {i}", "answer": "Reply", "evaluation": {"score": 20, "follow_up": "Probe retries"}} for i in range(2)],
                              difficulty=3, role="Engineer", job_description="", context="Career evidence", interview_type="technical")
    question = interview_ai.next_question(session)
    assert question["difficulty"] == 2
    assert captured[0]["prior_turns"][-1]["follow_up"] == "Probe retries"


def test_missing_interview_migration_returns_actionable_unavailable(client, resume_user, monkeypatch):
    monkeypatch.setattr("app.api.routes.interviews.schema_available", lambda db: False)
    response = client.get("/api/v1/interviews")
    assert response.status_code == 503
    assert "migration 20261023_0010" in response.json()["detail"]
    assert client.get("/api/v1/health").status_code == 200


def test_provider_timeout_is_explicit(monkeypatch):
    mock_http(monkeypatch)
    class TimeoutClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("Synthetic timeout")

    monkeypatch.setattr(interview_ai.httpx, "Client", lambda **kwargs: TimeoutClient())
    with pytest.raises(interview_ai.InterviewAIError) as exc:
        interview_ai.generate(Question, "Question", {})
    assert exc.value.status == 504
    assert "took too long" in str(exc.value)


def test_interview_upload_and_json_are_bounded_before_parsing(client):
    response = client.post("/api/v1/interviews/extract", files={"file": ("large.pdf", b"x" * (3 * 1024 * 1024 + 65536), "application/pdf")})
    assert response.status_code == 413
    response = client.post("/api/v1/interviews", content=b"x" * (512 * 1024 + 1), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
