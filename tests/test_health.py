def test_health_liveness_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"]


def test_health_readiness_endpoint(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ready"] is True
    assert payload["checks"]["metadata_store"]["ready"] is True
    assert payload["checks"]["vector_store"]["ready"] is True
    assert payload["checks"]["llm"]["ready"] is True
    assert payload["checks"]["embedding"]["ready"] is True


def test_health_readiness_returns_503_when_a_dependency_is_not_ready(client):
    async def fake_readiness_summary():
        return {
            "metadata_store": {"ready": True, "mode": "local"},
            "vector_store": {"ready": False, "mode": "local", "error": "broken"},
            "llm": {"ready": True, "mode": "fallback"},
            "embedding": {"ready": True, "mode": "fallback"},
        }

    client.app.state.services.readiness_summary = fake_readiness_summary

    response = client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["ready"] is False
    assert payload["checks"]["vector_store"]["error"] == "broken"


def test_health_readiness_returns_200_degraded_when_fallback_keeps_service_operational(client):
    async def fake_readiness_summary():
        return {
            "metadata_store": {"ready": True, "mode": "local"},
            "vector_store": {"ready": True, "mode": "local"},
            "llm": {
                "ready": False,
                "operational": True,
                "mode": "remote",
                "fallback_available": True,
                "error": "llm remote timeout",
            },
            "embedding": {
                "ready": False,
                "operational": True,
                "mode": "remote",
                "fallback_available": True,
                "error": "embedding remote timeout",
            },
        }

    client.app.state.services.readiness_summary = fake_readiness_summary

    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["ready"] is True
    assert payload["checks"]["llm"]["operational"] is True
    assert payload["checks"]["embedding"]["operational"] is True
