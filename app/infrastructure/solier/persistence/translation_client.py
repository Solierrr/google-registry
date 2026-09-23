"""Cliente HTTP das traduções de um registro real, hospedadas em `api-persistence`

Grava o resultado da tradução (`PUT /internal/translations/{entityTable}/{entityId}`)
"""

import logging
from urllib.parse import quote

from app.exceptions import InternalServiceException
from app.infrastructure.http.internal_http_client import InternalHttpClient
from app.schemas.i18n import TranslatedField

_log = logging.getLogger("google_registry.solier.translation_client")


class PersistenceTranslationClient:
    """Grava as traduções resolvidas pelo Google numa entidade real, via `api-persistence`."""

    def __init__(self, http_client: InternalHttpClient) -> None:
        self._http_client = http_client

    async def upsert_translations(self, entity_table: str, entity_id: str, translations: list[TranslatedField]) -> None:
        """Grava (ou atualiza) as traduções do registro em `api-persistence`"""
        try:
            await self._http_client.request(
                "PUT",
                f"/internal/translations/{quote(entity_table, safe='')}/{quote(entity_id, safe='')}",
                json={"translations": [field.model_dump() for field in translations]},
            )
        except InternalServiceException:
            _log.warning("Falha ao gravar traduções de %s/%s em api-persistence", entity_table, entity_id)
