"""Adapter da Routes API do Google (`directions/v2:computeRoutes`)

Único lugar que conhece o formato de request/response do Google para esta capability
"""

from datetime import UTC
from typing import Any

from app.domain.routes.ports import RoutesPort
from app.exceptions import GoogleNotFoundException, GoogleUpstreamException
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.routes import RouteOption, RouteRequest, RouteResponse

_COMPUTE_ROUTES_PATH = "/directions/v2:computeRoutes"
_FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
_MAX_ROUTES = 3


class RoutesAdapter(RoutesPort):
    """Implementação de `RoutesPort` sobre a Routes API do Google (`computeRoutes`)"""

    def __init__(self, http_client: GoogleHttpClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key

    async def compute_routes(self, request: RouteRequest) -> RouteResponse:
        """Consulta `computeRoutes` e traduz a resposta para `RouteResponse`

        Args:
            request: origem, destino, meio de transporte e preferências

        Returns:
            As rotas encontradas pelo Google (no máximo 3)

        Raises:
            GoogleNotFoundException: o Google não encontrou rota entre os pontos
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        response = await self._http_client.request(
            "POST",
            _COMPUTE_ROUTES_PATH,
            json=self._to_google_request(request),
            headers={"X-Goog-Api-Key": self._api_key, "X-Goog-FieldMask": _FIELD_MASK},
            retry=True,
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleUpstreamException(
                "Resposta da Routes API do Google em formato inesperado", capability="routes"
            ) from exc
        return self._to_route_response(payload)

    @staticmethod
    def _to_google_request(request: RouteRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "origin": {"location": {"latLng": request.origin.model_dump()}},
            "destination": {"location": {"latLng": request.destination.model_dump()}},
            "travelMode": request.travel_mode,
            "computeAlternativeRoutes": request.alternatives,
        }
        if request.travel_mode == "DRIVE":
            body["routingPreference"] = "TRAFFIC_AWARE"
            if request.departure_at is not None:
                departure = request.departure_at
                if departure.tzinfo is None:
                    departure = departure.replace(tzinfo=UTC)
                body["departureTime"] = departure.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            modifiers = {
                key: True
                for key, enabled in (("avoidTolls", request.avoid_tolls), ("avoidHighways", request.avoid_highways))
                if enabled
            }
            if modifiers:
                body["routeModifiers"] = modifiers
        return body

    @staticmethod
    def _to_route_response(payload: Any) -> RouteResponse:
        if not isinstance(payload, dict):
            raise GoogleUpstreamException("Resposta da Routes API do Google em formato inesperado", capability="routes")
        raw_routes = payload.get("routes")
        if not raw_routes:
            raise GoogleNotFoundException("Nenhuma rota encontrada entre os pontos", capability="routes")
        if not isinstance(raw_routes, list):
            raise GoogleUpstreamException("Resposta da Routes API do Google em formato inesperado", capability="routes")

        routes = [route for route in map(_to_route_option, raw_routes[:_MAX_ROUTES]) if route is not None]
        if not routes:
            raise GoogleUpstreamException("Resposta da Routes API do Google em formato inesperado", capability="routes")
        return RouteResponse(routes=routes)


def _to_route_option(raw: Any) -> RouteOption | None:
    """Traduz uma rota do Google, descartando as malformadas

    Args:
        raw: item de `routes` do payload do Google

    Returns:
        A rota, ou `None` se faltar `duration` ou `distanceMeters` ou se eles forem inválidos
    """
    if not isinstance(raw, dict):
        return None
    try:
        duration_seconds = int(float(str(raw["duration"]).removesuffix("s")))
        distance_meters = int(raw["distanceMeters"])
    except KeyError, TypeError, ValueError:
        return None
    polyline = raw.get("polyline")
    encoded = polyline.get("encodedPolyline") if isinstance(polyline, dict) else None
    return RouteOption(
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
        encoded_polyline=encoded if isinstance(encoded, str) else None,
    )
