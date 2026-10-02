"""Serviço de aplicação da capability de rotas

Orquestra o `RoutesPort`
"""

from app.domain.routes.ports import RoutesPort
from app.schemas.routes import RouteRequest, RouteResponse


class RoutesService:
    """Orquestra o provedor Google (`RoutesPort`)"""

    def __init__(self, port: RoutesPort) -> None:
        self._port = port

    async def compute_routes(self, request: RouteRequest) -> RouteResponse:
        """Calcula as rotas no Google

        Args:
            request: origem, destino, meio de transporte e preferências

        Returns:
            As rotas encontradas

        Raises:
            GoogleNotFoundException: nenhuma rota entre os pontos
        """
        return await self._port.compute_routes(request)
