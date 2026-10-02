"""Contrato da capability de rotas esperado"""

from typing import Protocol

from app.schemas.routes import RouteRequest, RouteResponse


class RoutesPort(Protocol):
    """Operações de rotas esperadas"""

    async def compute_routes(self, request: RouteRequest) -> RouteResponse:
        """Calcula rotas entre a origem e o destino

        Args:
            request: origem, destino, meio de transporte e preferências

        Returns:
            As rotas encontradas (no máximo 3)

        Raises:
            GoogleNotFoundException: nenhuma rota entre os pontos
        """
        ...
