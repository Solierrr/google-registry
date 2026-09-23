"""Contrato da capability de Solar esperado"""

from typing import Protocol

from app.schemas.solar import SolarViability


class SolarPort(Protocol):
    """Operações de viabilidade solar esperadas"""

    async def get_roof_viability(self, latitude: float, longitude: float) -> SolarViability:
        """Consulta a viabilidade solar do telhado mais próximo da coordenada informada

        Args:
            latitude: latitude do ponto a consultar
            longitude: longitude do ponto a consultar

        Returns:
            A viabilidade solar do telhado encontrado

        Raises:
            GoogleNotFoundException: sem dado de cobertura para a coordenada informada
        """
        ...
