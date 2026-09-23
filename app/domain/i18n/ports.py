"""Contrato da capability de i18n esperado"""

from typing import Protocol


class TranslationPort(Protocol):
    """Operações de detecção/tradução de idioma esperadas"""

    async def detect_language(self, text: str) -> str:
        """Detecta o idioma (ISO 639-1) do texto informado

        Args:
            text: texto no idioma de origem, ainda desconhecido

        Returns:
            O código do idioma detectado (ex.: "pt", "en", "es")

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        ...

    async def translate(self, text: str, target_language: str, *, source_language: str | None = None) -> str:
        """Traduz o texto para o idioma de destino

        Args:
            text: texto no idioma de origem
            target_language: idioma de destino (ISO 639-1)
            source_language: idioma de origem (ISO 639-1), se já conhecido

        Returns:
            O texto traduzido para `target_language`

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        ...
