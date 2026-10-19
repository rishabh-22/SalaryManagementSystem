# ruff: noqa: E501
from datetime import timedelta

from app.core.security import create_access_token
from tests.conftest import PASSWORD, headers_for


def login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def test_health_needs_no_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_login_success_returns_bearer_token(client, hr):
    r = login(client, hr.email)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]


def test_login_token_works_on_me(client, hr):
    token = login(client, hr.email).json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == hr.email and me["role"] == "hr_manager" and me["is_active"] is True
    assert "hashed_password" not in me and "password" not in me


def test_login_wrong_password_is_401(client, hr):
    r = login(client, hr.email, "wrong-password")
    assert r.status_code == 401 and "detail" in r.json()


def test_login_unknown_user_is_401(client):
    assert login(client, "nobody@test.com").status_code == 401


def test_login_inactive_user_is_401(client, make_user):
    user = make_user("viewer", is_active=False)
    assert login(client, user.email).status_code == 401


def test_login_rejects_json_body(client, hr):
    r = client.post("/api/auth/login", json={"username": hr.email, "password": PASSWORD})
    assert r.status_code == 422


def test_me_without_token_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_garbage_token_is_401(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_me_with_expired_token_is_401(client, hr):
    token = create_access_token(str(hr.id), hr.role, expires_delta=timedelta(seconds=-10))
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_with_token_for_deleted_user_is_401(client):
    token = create_access_token("9999", "admin")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_of_deactivated_user_is_rejected(client, db, hr):
    headers = headers_for(hr)
    hr.is_active = False
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_token_role_claim_cannot_escalate(client, viewer):
    """The role is read from the DB, not trusted from the JWT claim."""
    forged = create_access_token(str(viewer.id), "admin")
    r = client.get("/api/users", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403
