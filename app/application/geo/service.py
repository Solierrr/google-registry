from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.geo.ports import TimezonePort
from app.schemas.geo import TimezoneResponse


class GeoService:
    """Orquestra a descoberta de fuso horário"""

    def __init__(self, timezones: TimezonePort) -> None:
        self._timezones = timezones

    def get_timezone(self, latitude: float, longitude: float, at: datetime | None = None) -> TimezoneResponse | None:
        """Fuso horário de uma coordenada e o deslocamento do UTC no instante pedido

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto
            at: instante para calcular o deslocamento (omitido: agora; sem fuso, vale como UTC)

        Returns:
            O fuso e o deslocamento, ou `None` se não for possível determinar o fuso
        """
        timezone_id = self._timezones.timezone_at(latitude, longitude)
        if timezone_id is None:
            return None
        instant = at if at is not None else datetime.now(UTC)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        try:
            offset = ZoneInfo(timezone_id).utcoffset(instant)
        except ZoneInfoNotFoundError:
            return None
        return TimezoneResponse(
            timezone_id=timezone_id, utc_offset_seconds=int(offset.total_seconds()) if offset else 0
        )
