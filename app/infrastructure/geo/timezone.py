import tzfpy

from app.domain.geo.ports import TimezonePort


class TzfpyTimezoneFinder(TimezonePort):
    """Implementação de `TimezonePort` sobre a base de fusos embutida no `tzfpy`"""

    def timezone_at(self, latitude: float, longitude: float) -> str | None:
        """Identificador IANA do fuso da coordenada (no mar, `Etc/GMT±N`)

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto

        Returns:
            O identificador do fuso, ou `None` se não for possível determiná-lo
        """
        return tzfpy.get_tz(longitude, latitude) or None
