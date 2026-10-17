"""Regression tests for HTTP parsing behavior in the pinned ASGI stack."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def test_malformed_host_cannot_poison_starlette_request_url():
    """GHSA-86qp-5c8j-p5mr: Host must not rewrite request.url.path/hostname.

    Starlette 1.0.1 validates Host while reconstructing request.url and falls
    back to the ASGI server address when Host contains URL delimiters. This
    probe makes that security-sensitive value observable; production endpoints
    do not currently authorize based on request.url.
    """
    app = FastAPI()

    @app.get("/url-inspection")
    async def inspect_url(request: Request):
        return {"path": request.url.path, "hostname": request.url.hostname}

    response = TestClient(app).get(
        "/url-inspection",
        headers={"Host": "attacker.example/poison?query=1#fragment"},
    )

    assert response.status_code == 200
    assert response.json() == {"path": "/url-inspection", "hostname": "testserver"}
