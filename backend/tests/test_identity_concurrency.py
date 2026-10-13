"""Concurrent writes against an isolated clone of the actual users constraints."""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models.user import User
from app.schemas.auth import RegistrationRequest
from app.services.authentication import DuplicateIdentityError, authentication_service
from tests.test_auth import CONTEXT, registration_payload


@pytest.mark.parametrize("shared_identity", ["email", "uuid"])
def test_concurrent_identity_insert_is_database_enforced(shared_identity):
    schema = "auth_test_" + uuid4().hex
    assert re.fullmatch(r"auth_test_[a-f0-9]{32}", schema)
    engine = get_engine()
    # Only a newly created, uniquely named test schema is ever dropped below.
    # No public table or existing account is modified by this test.
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'CREATE TABLE "{schema}".users (LIKE public.users INCLUDING ALL)'))
    try:
        barrier = Barrier(2)
        identifier = uuid4()
        email = "race-" + uuid4().hex[:12] + "@example.com"
        translated = engine.execution_options(schema_translate_map={None: schema})
        def insert(index):
            with Session(translated) as db:
                barrier.wait(timeout=10)
                try:
                    if shared_identity == "email":
                        payload = RegistrationRequest(**{**registration_payload(), "email": email.upper() if index else email, "phone": None})
                        authentication_service.register(db, payload=payload, context=CONTEXT, verification_ttl=timedelta(minutes=5))
                    else:
                        db.add(User(id=identifier, email=f"race-{index}@example.com", username=f"race_{index}", full_name="Race Test User", is_active=False))
                    db.commit()
                    return "created"
                except (IntegrityError, DuplicateIdentityError):
                    db.rollback()
                    return "rejected"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(insert, [0,1]))
        assert sorted(results) == ["created", "rejected"]
        with Session(translated) as db:
            assert db.scalar(select(func.count()).select_from(User)) == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
