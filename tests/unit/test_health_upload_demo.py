from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.health import router


def test_upload_demo_reports_uploaded_body_size() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post(
        "/api/v1/health/upload-demo",
        content=b"hello upload",
        headers={"Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": 200,
        "data": {
            "fileSize": 12,
            "chunks": 1,
        },
    }


def test_multipart_upload_demo_reports_uploaded_body_metadata() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post(
        "/api/v1/health/upload-multipart-demo",
        files={"file": ("demo.txt", b"hello multipart", "text/plain")},
    )

    assert response.status_code == 200
    response_body = response.json()
    assert response_body["code"] == 200
    assert response_body["data"]["fileSize"] > len("hello multipart")
    assert response_body["data"]["chunks"] == 1
    assert response_body["data"]["contentType"].startswith("multipart/form-data")
