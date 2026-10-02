"""Testes de app.application.address.service.AddressService"""

from unittest.mock import AsyncMock

from app.application.address.service import AddressService
from app.schemas.address import Suggestion


async def test_suggest_wraps_suggestions_in_response():
    places = AsyncMock()
    places.suggest.return_value = [Suggestion(place_id="1", description="Rua A")]
    service = AddressService(places)

    result = await service.suggest("rua a", session_token="tok", language="pt-BR", country="BR")

    assert [s.place_id for s in result.suggestions] == ["1"]
    places.suggest.assert_awaited_once_with("rua a", session_token="tok", language="pt-BR", country="BR")
