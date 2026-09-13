"""Hierarquia de exceções da API

Adapters traduzem erros http vindo do google para consumers internos

cada classe tem um status code declarado
"""

from typing import Any


class GoogleProviderException(Exception):
    """Exceção base de qualquer erro

    transforma a mensagem para os consumers internos
    adiciona: nome da capablity que gerou o erro
    """

    http_status: int = 502
    #: Valor de `error.type` nas métricas desta exception
    error_type: str = "unknown"

    def __init__(self, message: str, *, capability: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.capability = capability
        self.status_code = status_code

    def details(self) -> dict[str, Any] | None:
        """Detalhes estruturados para o payload da exception (`None` = sem detalhes)"""
        return None


class GoogleAuthenticationException(GoogleProviderException):
    """api key google inválida | erro de config """

    http_status = 502
    error_type = "authentication"


class GoogleAuthorizationException(GoogleProviderException):
    """sem permissão ou consentimento para operação """

    http_status = 502
    error_type = "authorization"


class GoogleRateLimitException(GoogleProviderException):
    """quota do Google excedida para requests"""

    http_status = 503
    error_type = "rate_limit"


class GoogleValidationException(GoogleProviderException):
    """request rejeitada pelo Google por parâmetro obrigatório ausente ou malformado"""

    http_status = 400
    error_type = "validation"


class GoogleNotFoundException(GoogleProviderException):
    """dado não encontrado pelo Google """

    http_status = 404
    error_type = "not_found"


class GoogleTimeoutException(GoogleProviderException):
    """chamda pelo google excedeu o timeout configurado no client """

    http_status = 504
    error_type = "timeout"


class GoogleUnavailableException(GoogleProviderException):
    """falha do lado do Google após as tentativas de retry """

    http_status = 503
    error_type = "unavailable"


class GoogleUpstreamException(GoogleProviderException):
    """fallback para erro do Google não mapeado -> status HTTP inesperado ou payload HTTP 200 inválido"""

    http_status = 502
    error_type = "upstream"


class CalendarTokenRevokedException(GoogleProviderException):
    """O técnico revogou|não permitiu o consentimento OAuth do Calendar

    Não deve ser tentado novamente sem consentimento do técnico
    """

    http_status = 409
    error_type = "token_revoked"

    def __init__(self, message: str, *, technician_id: str) -> None:
        super().__init__(message, capability="calendar")
        self.technician_id = technician_id

    def details(self) -> dict[str, Any]:
        return {"technician_id": self.technician_id}
