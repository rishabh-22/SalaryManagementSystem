# ruff: noqa: E501
def test_meta_requires_auth(client):
    assert client.get("/api/meta").status_code == 401


def test_meta_shape(client, viewer_h):
    r = client.get("/api/meta", headers=viewer_h)
    assert r.status_code == 200
    body = r.json()
    assert {c["code"]: c["currency"] for c in body["countries"]} == {
        "US": "USD", "GB": "GBP", "IN": "INR", "DE": "EUR",
        "CA": "CAD", "SG": "SGD", "AU": "AUD", "BR": "BRL",
    }
    assert all("name" in c for c in body["countries"])
    assert "Engineering" in body["departments"] and body["job_titles"]
    assert body["employment_types"] == ["full_time", "part_time", "contract"]
    assert body["statuses"] == ["active", "terminated"]
    assert body["roles"] == ["admin", "hr_manager", "viewer"]
