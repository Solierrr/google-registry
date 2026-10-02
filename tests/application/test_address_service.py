"""Testes de app.application.address.service.AddressService"""

from unittest.mock import AsyncMock

from app.application.address.service import AddressService
from app.schemas.address import Suggestion


async def test_suggest_wraps_suggestions_in_response():
    places = AsyncMock()
    places.suggest.return_value = [Suggestion(place_id="1", description="Rua A")]
    service = AddressService(places, AsyncMock(), AsyncMock())

    result = await service.suggest("rua a", session_token="tok", language="pt-BR", country="BR")

    assert [s.place_id for s in result.suggestions] == ["1"]
    places.suggest.assert_awaited_once_with("rua a", session_token="tok", language="pt-BR", country="BR")


async def test_geocode_and_reverse_geocode_wrap_results():
    geocoding = AsyncMock()
    geocoding.geocode.return_value = []
    geocoding.reverse_geocode.return_value = []
    service = AddressService(AsyncMock(), geocoding, AsyncMock())

    assert (await service.geocode("rua a", language="pt-BR")).results == []
    assert (await service.reverse_geocode(-1.0, -2.0, language="pt-BR")).results == []
    geocoding.reverse_geocode.assert_awaited_once_with(-1.0, -2.0, language="pt-BR")
