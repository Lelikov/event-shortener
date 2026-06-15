"""Route-level integration tests against a real PostgreSQL (see conftest)."""

import re
import time


SHORTEN_URL = "/api/v1/urls/shorten"


def _payload(external_id: str, *, long_url: str = "https://meet.example.org/room/abc", **window) -> dict:
    return {"long_url": long_url, "external_id": external_id, "expires_at": None, "not_before": None, **window}


def test_shorten_returns_201_and_ident(client) -> None:
    resp = client.post(SHORTEN_URL, json=_payload("ext-1"))
    assert resp.status_code == 201
    ident = resp.json()["ident"]
    assert isinstance(ident, str)
    assert re.fullmatch(r"[a-z]{3}-[a-z]{3}-[a-z]{3}", ident)


def test_shorten_is_idempotent_by_external_id(client) -> None:
    first = client.post(SHORTEN_URL, json=_payload("ext-dup", long_url="https://a.example/1"))
    second = client.post(SHORTEN_URL, json=_payload("ext-dup", long_url="https://a.example/2"))
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["ident"] == second.json()["ident"]


def test_get_by_external_id_found_and_missing(client) -> None:
    created = client.post(SHORTEN_URL, json=_payload("ext-get"))
    ident = created.json()["ident"]

    found = client.get("/api/v1/urls/external/ext-get")
    assert found.status_code == 200
    assert found.json()["ident"] == ident

    missing = client.get("/api/v1/urls/external/nope")
    assert missing.status_code == 404


def test_patch_updates_fields_and_preserves_ident(client) -> None:
    created = client.post(SHORTEN_URL, json=_payload("ext-patch", long_url="https://old.example"))
    ident = created.json()["ident"]

    patched = client.patch(
        "/api/v1/urls/external/ext-patch",
        json=_payload("ext-patch-new", long_url="https://new.example"),
    )
    assert patched.status_code == 200
    assert patched.json()["ident"] == ident

    # external_id was changed: old gone, new resolves to the same ident.
    assert client.get("/api/v1/urls/external/ext-patch").status_code == 404
    assert client.get("/api/v1/urls/external/ext-patch-new").json()["ident"] == ident

    # long_url change is reflected in the redirect target.
    redirect = client.get(f"/{ident}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://new.example"


def test_patch_unknown_returns_404(client) -> None:
    resp = client.patch("/api/v1/urls/external/ghost", json=_payload("ghost2"))
    assert resp.status_code == 404


def test_delete_then_get_404(client) -> None:
    client.post(SHORTEN_URL, json=_payload("ext-del"))
    deleted = client.delete("/api/v1/urls/external/ext-del")
    assert deleted.status_code == 200
    assert deleted.json() == {}
    assert client.get("/api/v1/urls/external/ext-del").status_code == 404


def test_delete_unknown_is_idempotent_200(client) -> None:
    resp = client.delete("/api/v1/urls/external/never-existed")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_redirect_in_window_307(client) -> None:
    now = time.time()
    client.post(
        SHORTEN_URL,
        json=_payload("ext-ok", long_url="https://live.example", not_before=now - 60, expires_at=now + 3600),
    )
    ident = client.get("/api/v1/urls/external/ext-ok").json()["ident"]
    resp = client.get(f"/{ident}", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://live.example"


def test_redirect_expired_410(client) -> None:
    now = time.time()
    client.post(SHORTEN_URL, json=_payload("ext-exp", expires_at=now - 1))
    ident = client.get("/api/v1/urls/external/ext-exp").json()["ident"]
    resp = client.get(f"/{ident}", follow_redirects=False)
    assert resp.status_code == 410


def test_redirect_not_yet_active_410(client) -> None:
    now = time.time()
    client.post(SHORTEN_URL, json=_payload("ext-future", not_before=now + 3600))
    ident = client.get("/api/v1/urls/external/ext-future").json()["ident"]
    resp = client.get(f"/{ident}", follow_redirects=False)
    assert resp.status_code == 410


def test_redirect_unknown_404(client) -> None:
    resp = client.get("/abcdefg", follow_redirects=False)
    assert resp.status_code == 404


def test_redirect_open_window_307(client) -> None:
    # Both bounds null => always active.
    client.post(SHORTEN_URL, json=_payload("ext-open", long_url="https://open.example"))
    ident = client.get("/api/v1/urls/external/ext-open").json()["ident"]
    resp = client.get(f"/{ident}", follow_redirects=False)
    assert resp.status_code == 307


def test_redirect_increments_click_count(client) -> None:
    now = time.time()
    client.post(
        SHORTEN_URL,
        json=_payload("ext-clicks", long_url="https://live.example", not_before=now - 60, expires_at=now + 3600),
    )
    ident = client.get("/api/v1/urls/external/ext-clicks").json()["ident"]

    assert client.get(f"/api/v1/urls/{ident}/stats").json()["click_count"] == 0
    for _ in range(3):
        assert client.get(f"/{ident}", follow_redirects=False).status_code == 307
    assert client.get(f"/api/v1/urls/{ident}/stats").json()["click_count"] == 3


def test_expired_redirect_does_not_increment(client) -> None:
    now = time.time()
    client.post(
        SHORTEN_URL,
        json=_payload("ext-exp", long_url="https://gone.example", not_before=now - 120, expires_at=now - 60),
    )
    ident = client.get("/api/v1/urls/external/ext-exp").json()["ident"]
    assert client.get(f"/{ident}", follow_redirects=False).status_code == 410
    assert client.get(f"/api/v1/urls/{ident}/stats").json()["click_count"] == 0


def test_stats_unknown_ident_404(client) -> None:
    assert client.get("/api/v1/urls/abc-def-ghi/stats").status_code == 404
