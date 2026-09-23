"""Serviço de aplicação da capability de Solar

Orquestra o `SolarPort` e o perfil solar por unidade em `api-persistence`

Quando o unit_id é enviado junto, o resultado é gravado em api-persistece, como api-core
"""

from app.domain.solar.ports import SolarPort
from app.infrastructure.solier.persistence.unit_client import PersistenceUnitClient
from app.schemas.solar import SolarViability


class SolarService:
    """Orquestra o provedor Google (`SolarPort`) e o perfil solar por unidade em api-persistence"""

    def __init__(self, port: SolarPort, unit_client: PersistenceUnitClient) -> None:
        self._port = port
        self._unit_client = unit_client

    async def get_roof_viability(self, latitude: float, longitude: float, unit_id: str | None = None) -> SolarViability:
        """Consulta a viabilidade solar da coordenada no Google

        Args:
            latitude: latitude do ponto a consultar
            longitude: longitude do ponto a consultar
            unit_id: se informado, grava o resultado como perfil solar da `LocalUnit` em api-persistence
        Returns:
            A viabilidade solar do telhado mais próximo

        Raises:
            GoogleNotFoundException: sem dado de cobertura para a coordenada informada
        """
        result = await self._port.get_roof_viability(latitude, longitude)
        if unit_id is not None:
            await self._unit_client.upsert_solar_profile(unit_id, result)
        return result
