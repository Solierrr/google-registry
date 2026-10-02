from app.domain.solar.ports import SolarPort
from app.schemas.solar import SolarViability


class SolarService:
    """Orquestra o provedor Google (`SolarPort`)"""

    def __init__(self, port: SolarPort) -> None:
        self._port = port

    async def get_roof_viability(self, latitude: float, longitude: float) -> SolarViability:
        """Consulta a viabilidade solar da coordenada no Google

        Args:
            latitude: latitude do ponto a consultar
            longitude: longitude do ponto a consultar

        Returns:
            A viabilidade solar do telhado mais próximo

        Raises:
            GoogleNotFoundException: sem dado de cobertura para a coordenada informada
        """
        return await self._port.get_roof_viability(latitude, longitude)
