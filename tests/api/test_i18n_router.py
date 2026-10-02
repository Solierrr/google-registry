import httpx
import respx

BASE_URL = "https://translation.googleapis.com"


@respx.mock
def test_translate_returns_translations_without_writing_anywhere(client):
    respx.post(f"{BASE_URL}/language/translate/v2/detect").mock(
        return_value=httpx.Response(200, json={"data": {"detections": [[{"language": "pt"}]]}})
    )
    respx.post(f"{BASE_URL}/language/translate/v2").mock(
        return_value=httpx.Response(200, json={"data": {"translations": [{"translatedText": "Translated"}]}})
    )

    response = client.post("/v1/i18n/translate", json={"fields": [{"field_name": "title", "text": "Curso"}]})

    assert response.status_code == 200
    body = response.json()
    assert body["source_language"] == "pt"
    assert {t["language"] for t in body["translations"]} == {"en", "es"}


def test_translate_rejects_empty_fields(client):
    response = client.post("/v1/i18n/translate", json={"fields": []})

    assert response.status_code == 422
