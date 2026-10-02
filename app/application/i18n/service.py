from app.domain.i18n.ports import TranslationPort
from app.schemas.i18n import TranslatedField, TranslateResponse, TranslationField

SUPPORTED_LANGUAGES = ("en", "es", "pt")


class TranslationService:
    """Orquestra o provedor Google (`TranslationPort`)"""

    def __init__(self, port: TranslationPort) -> None:
        self._port = port

    async def translate_fields(
        self, fields: list[TranslationField], source_language: str | None = None
    ) -> TranslateResponse:
        """Detecta o idioma de origem (se não informado) e traduz os campos pros demais idiomas suportados

        Args:
            fields: campos de texto a traduzir
            source_language: idioma de origem (ISO 639-1), se já conhecido

        Returns:
            As traduções geradas, uma por campo e idioma de destino

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        detected_language = source_language or await self._port.detect_language(fields[0].text)
        target_languages = [language for language in SUPPORTED_LANGUAGES if language != detected_language]
        texts = [field.text for field in fields]

        translated: list[TranslatedField] = []
        for target_language in target_languages:
            values = await self._port.translate_batch(texts, target_language, source_language=detected_language)
            translated.extend(
                TranslatedField(field_name=field.field_name, language=target_language, value=value)
                for field, value in zip(fields, values, strict=True)
            )

        return TranslateResponse(source_language=detected_language, translations=translated)
