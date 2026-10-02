import pytest

from app.infrastructure.geo.timezone import TzfpyTimezoneFinder


@pytest.mark.parametrize(
    ("latitude", "longitude", "timezone_id"),
    [
        (-23.55, -46.63, "America/Sao_Paulo"),
        (-3.1, -60.0, "America/Manaus"),
        (-9.97, -67.8, "America/Rio_Branco"),
        (-15.6, -56.1, "America/Cuiaba"),
    ],
)
def test_finds_the_brazilian_timezones(latitude, longitude, timezone_id):
    assert TzfpyTimezoneFinder().timezone_at(latitude, longitude) == timezone_id


def test_uses_longitude_and_latitude_in_the_right_order():
    # Lisboa: se os eixos estivessem trocados, o ponto cairia em outro lugar do mundo
    assert TzfpyTimezoneFinder().timezone_at(38.72, -9.14) == "Europe/Lisbon"


def test_open_sea_has_an_etc_zone():
    assert TzfpyTimezoneFinder().timezone_at(-23.0, -30.0).startswith("Etc/GMT")
