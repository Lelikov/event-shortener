"""Auth on /api/v1/* only; the public redirect + ops endpoints stay open."""

from tests.conftest import API_KEY


def _payload(external_id: str) -> dict:
    return {"long_url": "https://x.example", "external_id": external_id, "expires_at": None, "not_before": None}


def test_missing_key_rejected(unauth_client) -> None:
    resp = unauth_client.post("/api/v1/urls/shorten", json=_payload("a"))
    assert resp.status_code == 401


def test_wrong_key_rejected(unauth_client) -> None:
    resp = unauth_client.post(
        "/api/v1/urls/shorten",
        json=_payload("a"),
        headers={"Authorization": "Bearer not-the-key"},
    )
    assert resp.status_code == 401


def test_correct_key_accepted(unauth_client) -> None:
    resp = unauth_client.post(
        "/api/v1/urls/shorten",
        json=_payload("auth-ok"),
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert resp.status_code == 201


def test_get_external_requires_key(unauth_client) -> None:
    assert unauth_client.get("/api/v1/urls/external/x").status_code == 401


def test_health_is_public(unauth_client) -> None:
    assert unauth_client.get("/health").status_code == 200


def test_ready_is_public(unauth_client) -> None:
    # DB is up in the harness, so readiness reports ready without a key.
    resp = unauth_client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_metrics_is_public(unauth_client) -> None:
    resp = unauth_client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text or resp.text == ""


def test_redirect_is_public(unauth_client) -> None:
    auth = {"Authorization": f"Bearer {API_KEY}"}
    unauth_client.post(
        "/api/v1/urls/shorten",
        json={"long_url": "https://pub.example", "external_id": "pub", "expires_at": None, "not_before": None},
        headers=auth,
    )
    ident = unauth_client.get("/api/v1/urls/external/pub", headers=auth).json()["ident"]
    # No auth header on the redirect itself: it must still resolve.
    resp = unauth_client.get(f"/{ident}", follow_redirects=False)
    assert resp.status_code == 307
