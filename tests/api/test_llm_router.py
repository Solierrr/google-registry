import pytest


@pytest.fixture
def keys_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY_1", "gem-secret-1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "gem-secret-2")
    monkeypatch.setenv("GROQ_API_KEY_1", "groq-secret-1")


def test_lease_returns_key_base_url_and_ready_to_use_header(keys_env, client):
    response = client.get("/v1/llm/keys", params={"provider": "groq"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "groq"
    assert body["api_key"] == "groq-secret-1"
    assert body["base_url"] == "https://api.groq.com/openai/v1"
    assert body["auth_header"] == {"name": "Authorization", "value": "Bearer groq-secret-1"}
    assert body["key_id"].startswith("groq-")
    assert "groq-secret-1" not in body["key_id"]


def test_lease_for_gemini_uses_the_google_header(keys_env, client):
    body = client.get("/v1/llm/keys", params={"provider": "gemini"}).json()

    assert body["auth_header"] == {"name": "x-goog-api-key", "value": body["api_key"]}


def test_lease_rotates_between_keys_and_providers(keys_env, client):
    secrets = [client.get("/v1/llm/keys").json()["api_key"] for _ in range(4)]

    assert secrets == ["gem-secret-1", "gem-secret-2", "groq-secret-1", "gem-secret-1"]


def test_lease_for_embedding_never_returns_groq(keys_env, client):
    providers = {client.get("/v1/llm/keys", params={"purpose": "embedding"}).json()["provider"] for _ in range(4)}

    assert providers == {"gemini"}


def test_lease_without_any_configured_key_is_404(client):
    response = client.get("/v1/llm/keys")

    assert response.status_code == 404
    assert response.json()["code"] == "LlmKeysNotConfiguredException"


def test_lease_rejects_unknown_provider(keys_env, client):
    assert client.get("/v1/llm/keys", params={"provider": "openai"}).status_code == 422


@pytest.fixture
def single_key_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY_1", "only-key")


def test_rate_limited_report_makes_the_key_rest_and_all_resting_returns_503_with_retry_after(single_key_env, client):
    key_id = client.get("/v1/llm/keys").json()["key_id"]

    report = client.post(f"/v1/llm/keys/{key_id}/report", json={"outcome": "rate_limited", "retry_after_seconds": 30})
    response = client.get("/v1/llm/keys")

    assert report.status_code == 204
    assert response.status_code == 503
    assert response.json()["code"] == "LlmKeysUnavailableException"
    assert response.headers["Retry-After"] == "30"
    assert response.json()["details"] == {"retry_after_seconds": 30}


def test_report_of_unknown_key_is_404(keys_env, client):
    response = client.post("/v1/llm/keys/gemini-unknown/report", json={"outcome": "ok"})

    assert response.status_code == 404
    assert response.json()["code"] == "LlmKeyNotFoundException"


def test_report_rejects_invalid_outcome(keys_env, client):
    key_id = client.get("/v1/llm/keys").json()["key_id"]

    assert client.post(f"/v1/llm/keys/{key_id}/report", json={"outcome": "boom"}).status_code == 422
    assert (
        client.post(
            f"/v1/llm/keys/{key_id}/report", json={"outcome": "rate_limited", "retry_after_seconds": 0}
        ).status_code
        == 422
    )


def test_providers_lists_key_states_without_secrets(keys_env, client):
    key_id = client.get("/v1/llm/keys", params={"provider": "groq"}).json()["key_id"]
    client.post(f"/v1/llm/keys/{key_id}/report", json={"outcome": "invalid"})

    response = client.get("/v1/llm/providers")

    assert response.status_code == 200
    by_provider = {p["provider"]: p["keys"] for p in response.json()["providers"]}
    assert len(by_provider["gemini"]) == 2
    assert by_provider["groq"][0]["status"] == "invalid"
    assert "secret" not in response.text
