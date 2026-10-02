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


def _address(**overrides):
    from app.schemas.address import Address

    return Address(
        **{
            "formatted_address": "Av. Paulista, 1000, São Paulo - SP",
            "latitude": -23.5,
            "longitude": -46.6,
            "city": "São Paulo",
            "state": "SP",
            "postal_code": "01310-100",
            "country_code": "BR",
            **overrides,
        }
    )


def _validation(verdict="ok"):
    from app.schemas.address import ValidateResponse

    return ValidateResponse(verdict=verdict, unconfirmed_components=["street_number"])


async def test_resolve_by_place_id_uses_place_details_and_validates_the_address():
    places, geocoding, validation = AsyncMock(), AsyncMock(), AsyncMock()
    places.get_details.return_value = _address()
    validation.validate.return_value = _validation("needs_review")
    service = AddressService(places, geocoding, validation)

    result = await service.resolve(place_id="ChIJ1", query=None, session_token="tok", language="pt-BR")

    assert result.address.postal_code == "01310-100"
    assert result.validation is not None
    assert result.validation.verdict == "needs_review"
    assert result.validation.unconfirmed_components == ["street_number"]
    places.get_details.assert_awaited_once_with("ChIJ1", session_token="tok", language="pt-BR")
    geocoding.geocode.assert_not_called()
    sent = validation.validate.await_args.args[0]
    assert sent.address_lines == ["Av. Paulista, 1000, São Paulo - SP"]
    assert (sent.postal_code, sent.locality, sent.administrative_area, sent.region_code) == (
        "01310-100",
        "São Paulo",
        "SP",
        "BR",
    )


async def test_resolve_by_query_uses_the_first_geocoding_result():
    places, geocoding, validation = AsyncMock(), AsyncMock(), AsyncMock()
    geocoding.geocode.return_value = [_address(formatted_address="Primeiro"), _address(formatted_address="Segundo")]
    validation.validate.return_value = _validation()
    service = AddressService(places, geocoding, validation)

    result = await service.resolve(place_id=None, query="paulista 1000", session_token=None, language="pt-BR")

    assert result.address.formatted_address == "Primeiro"
    places.get_details.assert_not_called()


async def test_resolve_by_query_without_results_is_not_found():
    import pytest

    from app.exceptions import GoogleNotFoundException

    geocoding = AsyncMock()
    geocoding.geocode.return_value = []
    service = AddressService(AsyncMock(), geocoding, AsyncMock())

    with pytest.raises(GoogleNotFoundException):
        await service.resolve(place_id=None, query="zzz zzz", session_token=None, language="pt-BR")


async def test_resolve_returns_address_without_validation_when_validation_fails():
    from app.exceptions import GoogleUnavailableException

    places, validation = AsyncMock(), AsyncMock()
    places.get_details.return_value = _address()
    validation.validate.side_effect = GoogleUnavailableException("fora do ar", capability="address_validation")
    service = AddressService(places, AsyncMock(), validation)

    result = await service.resolve(place_id="ChIJ1", query=None, session_token=None, language="pt-BR")

    assert result.address.formatted_address.startswith("Av. Paulista")
    assert result.validation is None
