# ruff: noqa: E501
from app.core.security import verify_password
from app.models import User
from tests.conftest import PASSWORD

URL = "/api/users"


def new_user(**over):
    body = {"email": "new@test.com", "full_name": "New Person", "password": "LongEnough1!", "role": "viewer"}
    body.update(over)
    return body


def test_list_users_ordered_by_id_without_password(client, admin, admin_h, make_user):
    make_user("viewer", email="v@test.com")
    r = client.get(URL, headers=admin_h)
    assert r.status_code == 200
    users = r.json()
    assert [u["id"] for u in users] == sorted(u["id"] for u in users)
    assert {u["email"] for u in users} == {"admin@test.com", "v@test.com"}
    assert all("hashed_password" not in u and "password" not in u for u in users)


def test_create_user_hashes_password_and_can_login(client, db, admin_h):
    r = client.post(URL, json=new_user(role="hr_manager"), headers=admin_h)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@test.com" and body["role"] == "hr_manager" and body["is_active"] is True
    stored = db.query(User).filter_by(email="new@test.com").one()
    assert stored.hashed_password != "LongEnough1!" and verify_password("LongEnough1!", stored.hashed_password)
    login = client.post("/api/auth/login", data={"username": "new@test.com", "password": "LongEnough1!"})
    assert login.status_code == 200


def test_create_duplicate_email_is_409(client, admin_h):
    assert client.post(URL, json=new_user(), headers=admin_h).status_code == 201
    assert client.post(URL, json=new_user(full_name="Dup"), headers=admin_h).status_code == 409


def test_create_validation(client, admin_h):
    for over in ({"password": "short"}, {"email": "bad"}, {"role": "root"}, {"full_name": ""}):
        assert client.post(URL, json=new_user(**over), headers=admin_h).status_code == 422, over


def test_patch_user_fields_and_password(client, db, admin_h, make_user):
    target = make_user("viewer", email="t@test.com")
    r = client.patch(
        f"{URL}/{target.id}",
        json={"full_name": "Renamed", "role": "hr_manager", "is_active": False, "password": "BrandNew#123"},
        headers=admin_h,
    )
    assert r.status_code == 200
    assert (r.json()["full_name"], r.json()["role"], r.json()["is_active"]) == ("Renamed", "hr_manager", False)
    db.expire_all()
    assert verify_password("BrandNew#123", db.get(User, target.id).hashed_password)


def test_patch_short_password_is_422(client, admin_h, make_user):
    target = make_user("viewer")
    assert client.patch(f"{URL}/{target.id}", json={"password": "x"}, headers=admin_h).status_code == 422


def test_patch_unknown_user_is_404(client, admin_h):
    assert client.patch(f"{URL}/999", json={"full_name": "x"}, headers=admin_h).status_code == 404


def test_delete_user(client, admin_h, make_user):
    target = make_user("viewer")
    assert client.delete(f"{URL}/{target.id}", headers=admin_h).status_code == 204
    ids = [u["id"] for u in client.get(URL, headers=admin_h).json()]
    assert target.id not in ids


def test_delete_unknown_user_is_404(client, admin_h):
    assert client.delete(f"{URL}/999", headers=admin_h).status_code == 404


def test_deactivated_user_cannot_login(client, admin_h, make_user):
    target = make_user("viewer", email="soon@test.com")
    client.patch(f"{URL}/{target.id}", json={"is_active": False}, headers=admin_h)
    r = client.post("/api/auth/login", data={"username": "soon@test.com", "password": PASSWORD})
    assert r.status_code == 401


# ---------- self protection ----------

def test_admin_cannot_delete_self(client, admin, admin_h):
    assert client.delete(f"{URL}/{admin.id}", headers=admin_h).status_code == 400
    assert client.get("/api/auth/me", headers=admin_h).status_code == 200


def test_admin_cannot_deactivate_self(client, admin, admin_h):
    assert client.patch(f"{URL}/{admin.id}", json={"is_active": False}, headers=admin_h).status_code == 400


def test_admin_cannot_change_own_role(client, admin, admin_h):
    assert client.patch(f"{URL}/{admin.id}", json={"role": "viewer"}, headers=admin_h).status_code == 400
    assert client.get("/api/auth/me", headers=admin_h).json()["role"] == "admin"


def test_admin_can_edit_own_name_and_password(client, admin, admin_h):
    r = client.patch(f"{URL}/{admin.id}", json={"full_name": "Boss", "password": "Another#1234"}, headers=admin_h)
    assert r.status_code == 200 and r.json()["full_name"] == "Boss"


def test_admin_can_set_own_role_to_same_value(client, admin, admin_h):
    r = client.patch(f"{URL}/{admin.id}", json={"role": "admin"}, headers=admin_h)
    assert r.status_code in (200, 400)  # contract: "change the role"; same value is ambiguous
