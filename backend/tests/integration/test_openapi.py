from __future__ import annotations

from fastapi.testclient import TestClient


def test_every_operation_is_documented(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            label = f"{method.upper()} {path}"
            assert operation.get("summary"), label
            assert operation.get("description"), label
            assert any(code.startswith("2") for code in operation["responses"]), label


def test_error_responses_document_the_envelope_with_examples(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    upload = spec["paths"]["/api/files/"]["post"]["responses"]
    assert {"400", "413", "415", "422", "500"} <= set(upload)
    examples = upload["400"]["content"]["application/json"]["examples"]
    assert (
        examples["missing_components"]["value"]["error"]["code"] == "MISSING_SHAPEFILE_COMPONENTS"
    )

    measurements = spec["paths"]["/api/files/{file_id}/measurements/"]["get"]["responses"]
    assert {"404", "409", "422"} <= set(measurements)


def test_docs_alias_redirects_to_swagger(client: TestClient) -> None:
    response = client.get("/docs", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/api/docs"
    assert client.get("/api/docs").status_code == 200
