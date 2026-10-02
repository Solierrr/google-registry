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

    async def translate_batch(
        self, texts: list[str], target_language: str, *, source_language: str | None = None
    ) -> list[str]:
        """Traduz vários textos para o idioma de destino em uma única chamada

        Args:
            texts: textos no idioma de origem
            target_language: idioma de destino (ISO 639-1)
            source_language: idioma de origem (ISO 639-1), se já conhecido

        Returns:
            Os textos traduzidos para `target_language`, na mesma ordem de `texts`

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        ...
