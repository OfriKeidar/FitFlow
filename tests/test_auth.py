from datetime import datetime, timedelta, timezone

from fitflow.services.auth import create_token, hash_password, verify_password
from tests.conftest import PROFILE, register


def test_password_is_hashed_with_a_random_salt():
    first, second = hash_password("secret123"), hash_password("secret123")
    assert "secret123" not in first
    assert first != second  # different salt -> different hash
    assert verify_password("secret123", first) and not verify_password("wrong", first)


def test_register_then_login(client):
    register(client, email="Noa@Example.com")
    r = client.post("/auth/login", json={"email": "noa@example.com", "password": "secret123"})
    assert r.status_code == 200
    assert client.get("/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()["name"] == "Dana"


def test_wrong_password_and_unknown_email_look_the_same(client):
    register(client)
    wrong_password = client.post("/auth/login", json={"email": "dana@example.com", "password": "nope-nope"})
    unknown_email = client.post("/auth/login", json={"email": "who@example.com", "password": "secret123"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_email_can_only_register_once(client):
    register(client)
    body = PROFILE | {"email": "dana@example.com", "password": "secret123"}
    assert client.post("/auth/register", json=body).status_code == 409


def test_short_password_is_rejected(client):
    body = PROFILE | {"email": "a@example.com", "password": "short"}
    assert client.post("/auth/register", json=body).status_code == 422


def test_requests_without_a_valid_token_get_401(client):
    assert client.get("/today").status_code == 401
    assert client.get("/today", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_forged_and_expired_tokens_are_rejected(client, user):
    user_id = client.get("/me", headers=user).json()["id"]
    forged = create_token(user_id)[:-2] + "xx"  # tampered signature
    expired = create_token(user_id, now=datetime.now(timezone.utc) - timedelta(days=8))
    for token in (forged, expired):
        assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
