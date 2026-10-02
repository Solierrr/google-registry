"""Testes de app.application.geo.service.GeoService"""

from datetime import UTC, datetime, timedelta, timezone

from app.application.geo.service import GeoService


class FakeTimezones:
    def __init__(self, timezone_id):
        self._timezone_id = timezone_id

    def timezone_at(self, latitude, longitude):
        return self._timezone_id


def test_offset_is_calculated_at_the_requested_instant():
    service = GeoService(FakeTimezones("America/Manaus"))

    result = service.get_timezone(-3.1, -60.0, datetime(2026, 7, 1, 12, 0, tzinfo=UTC))

    assert (result.timezone_id, result.utc_offset_seconds) == ("America/Manaus", -4 * 3600)


def test_offset_follows_daylight_saving_time_of_the_zone():
    service = GeoService(FakeTimezones("Europe/Lisbon"))

    summer = service.get_timezone(38.7, -9.1, datetime(2026, 7, 1, tzinfo=UTC))
    winter = service.get_timezone(38.7, -9.1, datetime(2026, 1, 1, tzinfo=UTC))

    assert (summer.utc_offset_seconds, winter.utc_offset_seconds) == (3600, 0)


def test_instant_without_timezone_is_treated_as_utc():
    service = GeoService(FakeTimezones("Asia/Kolkata"))

    naive = service.get_timezone(0, 0, datetime(2026, 1, 1, 0, 0))
    aware = service.get_timezone(0, 0, datetime(2026, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=-3))))

    assert naive.utc_offset_seconds == aware.utc_offset_seconds == 19800


def test_defaults_to_now_when_no_instant_is_given():
    result = GeoService(FakeTimezones("America/Sao_Paulo")).get_timezone(-23.5, -46.6)

    assert result.utc_offset_seconds == -3 * 3600


def test_unknown_coordinate_or_zone_gives_none():
    assert GeoService(FakeTimezones(None)).get_timezone(0, 0) is None
    assert GeoService(FakeTimezones("Mars/Olympus")).get_timezone(0, 0) is None
