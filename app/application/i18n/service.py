"""Serviço de aplicação da capability de i18n

Orquestra o `TranslationPort`

Idiomas suportados pela plataforma: inglês (en), espanhol (es) e português (pt).
O idioma de origem é excluído da lista de destinos - um registro nunca é
"traduzido" para o próprio idioma.
"""

from app.domain.i18n.ports import TranslationPort
from app.schemas.i18n import TranslatedField, TranslateResponse, TranslationField

SUPPORTED_LANGUAGES = ("en", "es", "pt")


class TranslationService:
    """Orquestra o provedor Google (`TranslationPort`)"""

    def __init__(self, port: TranslationPort) -> None:
        self._port = port

    async def translate_entity(
        self,
        entity_table: str,
        entity_id: str,
        fields: list[TranslationField],
        source_language: str | None = None,
    ) -> TranslateResponse:
        """Detecta o idioma de origem (se não informado) e traduz os campos pros demais idiomas suportados

        Args:
            entity_table: tabela de origem em api-core
            entity_id: id do registro em api-core
            fields: campos de texto a traduzir
            source_language: idioma de origem (ISO 639-1), se já conhecido

        Returns:
            As traduções geradas

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        detected_language = source_language or await self._port.detect_language(fields[0].text)
        target_languages = [language for language in SUPPORTED_LANGUAGES if language != detected_language]

        translated: list[TranslatedField] = []
        for field in fields:
            for target_language in target_languages:
                value = await self._port.translate(field.text, target_language, source_language=detected_language)
                translated.append(TranslatedField(field_name=field.field_name, language=target_language, value=value))

        return TranslateResponse(
            entity_table=entity_table,
            entity_id=entity_id,
            source_language=detected_language,
            translations=translated,
        )
