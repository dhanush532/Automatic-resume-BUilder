from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db_session, get_engine
from app.integrations.email import get_email_provider
from app.main import app


class TestEmailProvider:
    __test__ = False
    name = "test-only"
    is_configured = True
    supports_idempotency = True

    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return "test-provider-accepted"


@pytest.fixture(autouse=True)
def test_email_provider(monkeypatch):
    provider = TestEmailProvider()
    app.dependency_overrides[get_email_provider] = lambda: provider
    # Never send or enqueue external messages from automatic tests.
    monkeypatch.setattr("app.api.routes.auth.publish_email", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.api.routes.account.publish_email", lambda *args, **kwargs: True)
    yield provider
    app.dependency_overrides.pop(get_email_provider, None)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    # Application commits release savepoints, never the enclosing transaction.
    # Test data and explicit cleanup are rolled back, even after assertions fail.
    with get_engine().connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint") as session:
            def override_db() -> Generator[Session, None, None]:
                yield session

            app.dependency_overrides[get_db_session] = override_db
            try:
                yield session
            finally:
                app.dependency_overrides.pop(get_db_session, None)
                session.close()
                transaction.rollback()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
