from unittest.mock import AsyncMock

import pytest

from app.application.i18n.service import TranslationService
from app.schemas.i18n import TranslationField


@pytest.fixture
def port():
    port = AsyncMock()
    port.detect_language.return_value = "pt"
    port.translate_batch.side_effect = lambda texts, target_language, source_language=None: [
        f"{text}-{target_language}" for text in texts
    ]
    return port


async def test_translates_into_the_other_two_supported_languages(port):
    service = TranslationService(port)
    fields = [TranslationField(field_name="information", text="Curso de NR-10")]

    result = await service.translate_fields(fields)

    assert result.source_language == "pt"
    assert {t.language for t in result.translations} == {"en", "es"}
    assert len(result.translations) == 2


async def test_does_not_call_detect_when_source_language_is_given(port):
    service = TranslationService(port)
    fields = [TranslationField(field_name="information", text="NR-10 course")]

    result = await service.translate_fields(fields, source_language="en")

    port.detect_language.assert_not_called()
    assert result.source_language == "en"
    assert {t.language for t in result.translations} == {"es", "pt"}


async def test_translates_all_fields_in_one_call_per_target_language(port):
    service = TranslationService(port)
    fields = [
        TranslationField(field_name="title", text="Curso"),
        TranslationField(field_name="information", text="Texto"),
    ]

    result = await service.translate_fields(fields)

    assert port.detect_language.await_count == 1
    assert port.translate_batch.await_count == 2
    by_key = {(t.field_name, t.language): t.value for t in result.translations}
    assert by_key[("title", "en")] == "Curso-en"
    assert by_key[("information", "es")] == "Texto-es"
    assert len(result.translations) == 4
