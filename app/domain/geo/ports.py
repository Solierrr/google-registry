from typing import Protocol


class TimezonePort(Protocol):
    """Descoberta do fuso horário de uma coordenada"""

    def timezone_at(self, latitude: float, longitude: float) -> str | None:
        """Identificador IANA do fuso da coordenada

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto

        Returns:
            O identificador do fuso (ex.: America/Manaus), ou `None` se não for possível determiná-lo
        """
        ...
