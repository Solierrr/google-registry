"""Adapter da Cloud Translation API do Google (v2, `detect` + `translate`)

Único lugar que conhece o formato de request/response do Google para esta capability
"""

from typing import Any

from app.domain.i18n.ports import TranslationPort
from app.exceptions import GoogleUpstreamException
from app.infrastructure.http.google_http_client import GoogleHttpClient

_DETECT_PATH = "/language/translate/v2/detect"
_TRANSLATE_PATH = "/language/translate/v2"


class TranslationAdapter(TranslationPort):
    """Implementação de `TranslationPort` sobre a Cloud Translation API do Google (v2)"""

    def __init__(self, http_client: GoogleHttpClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key

    async def detect_language(self, text: str) -> str:
        """Consulta `language/translate/v2/detect` e retorna o idioma mais provável

        Args:
            text: texto no idioma de origem, ainda desconhecido

        Returns:
            O código do idioma detectado (ex.: "pt", "en", "es")

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        response = await self._http_client.request(
            "POST", _DETECT_PATH, json={"q": text}, headers={"X-Goog-Api-Key": self._api_key}, retry=True
        )
        payload = self._parse_json(response)
        try:
            return payload["data"]["detections"][0][0]["language"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GoogleUpstreamException(
                "Resposta da Translation API do Google em formato inesperado", capability="translation"
            ) from exc

    async def translate_batch(
        self, texts: list[str], target_language: str, *, source_language: str | None = None
    ) -> list[str]:
        """Consulta `language/translate/v2` com vários textos e retorna as traduções na mesma ordem

        Args:
            texts: textos no idioma de origem
            target_language: idioma de destino (ISO 639-1)
            source_language: idioma de origem (ISO 639-1), se já conhecido

        Returns:
            Os textos traduzidos para `target_language`, na mesma ordem de `texts`

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        body: dict[str, Any] = {"q": texts, "target": target_language, "format": "text"}
        if source_language is not None:
            body["source"] = source_language

        response = await self._http_client.request(
            "POST", _TRANSLATE_PATH, json=body, headers={"X-Goog-Api-Key": self._api_key}, retry=True
        )
        payload = self._parse_json(response)
        try:
            translated = [item["translatedText"] for item in payload["data"]["translations"]]
        except (KeyError, TypeError) as exc:
            raise GoogleUpstreamException(
                "Resposta da Translation API do Google em formato inesperado", capability="translation"
            ) from exc
        if len(translated) != len(texts):
            raise GoogleUpstreamException(
                "Resposta da Translation API do Google em formato inesperado", capability="translation"
            )
        return translated

    @staticmethod
    def _parse_json(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise GoogleUpstreamException(
                "Resposta da Translation API do Google em formato inesperado", capability="translation"
            ) from exc
