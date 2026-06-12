import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def gated_client(conn):
    os.environ["PMAI_PASSWORD"] = "demo123"
    try:
        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("PMAI_PASSWORD", None)


def test_no_password_means_no_gate(conn):
    with TestClient(app) as c:
        assert c.get("/", follow_redirects=False).status_code == 200
        # /login redirects home when the gate is off
        assert c.get("/login", follow_redirects=False).status_code == 303


def test_gate_blocks_until_login(gated_client):
    resp = gated_client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    # wrong password stays out
    resp = gated_client.post("/login", data={"password": "nope"}, follow_redirects=False)
    assert "error=1" in resp.headers["location"]
    # right password gets a cookie and access
    resp = gated_client.post("/login", data={"password": "demo123"}, follow_redirects=False)
    assert resp.status_code == 303 and "pmai_auth" in resp.headers.get("set-cookie", "")
    assert gated_client.get("/", follow_redirects=False).status_code == 200
