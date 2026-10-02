"""Testes de app.application.i18n.service.TranslationService"""

from unittest.mock import AsyncMock

import pytest

from app.application.i18n.service import TranslationService
from app.schemas.i18n import TranslationField


@pytest.fixture
def port():
    port = AsyncMock()
    port.detect_language.return_value = "pt"
    port.translate.side_effect = lambda text, target_language, source_language=None: f"{text}-{target_language}"
    return port


async def test_translates_into_the_other_two_supported_languages(port):
    service = TranslationService(port)
    fields = [TranslationField(field_name="information", text="Curso de NR-10")]

    result = await service.translate_entity("technical_course", "11111111-1111-1111-1111-111111111111", fields)

    assert result.source_language == "pt"
    assert {t.language for t in result.translations} == {"en", "es"}
    assert len(result.translations) == 2


async def test_does_not_call_detect_when_source_language_is_given(port):
    service = TranslationService(port)
    fields = [TranslationField(field_name="information", text="NR-10 course")]

    result = await service.translate_entity(
        "technical_course", "11111111-1111-1111-1111-111111111111", fields, source_language="en"
    )

    port.detect_language.assert_not_called()
    assert result.source_language == "en"
    assert {t.language for t in result.translations} == {"es", "pt"}
