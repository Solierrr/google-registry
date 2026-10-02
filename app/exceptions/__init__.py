from typing import Any


class GoogleProviderException(Exception):
    """Exceção base de qualquer erro

    transforma a mensagem para os consumers internos
    adiciona: nome da capablity que gerou o erro
    """

    http_status: int = 502
    #: Valor de `error.type` nas métricas desta exception
    error_type: str = "unknown"

    def __init__(
        self, message: str, *, capability: str, status_code: int | None = None, reason: str | None = None
    ) -> None:
        super().__init__(message)
        self.capability = capability
        self.status_code = status_code
        #: Motivo estruturado devolvido pelo Google
        self.reason = reason

    def details(self) -> dict[str, Any] | None:
        """Detalhes estruturados para o payload da exception (`None` = sem detalhes)"""
        return None


class GoogleAuthenticationException(GoogleProviderException):
    """api key google inválida | erro de config"""

    http_status = 502
    error_type = "authentication"


class GoogleAuthorizationException(GoogleProviderException):
    """sem permissão ou consentimento para operação"""

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
    """dado não encontrado pelo Google"""

    http_status = 404
    error_type = "not_found"


class GoogleTimeoutException(GoogleProviderException):
    """chamda pelo google excedeu o timeout configurado no client"""

    http_status = 504
    error_type = "timeout"


class GoogleUnavailableException(GoogleProviderException):
    """falha do lado do Google após as tentativas de retry"""

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


class InternalServiceException(Exception):
    """Exceção base de erro ao chamar um serviço interno Solier (api-auth)"""

    http_status: int = 502
    #: Valor de `error.type` nas métricas desta exception
    error_type: str = "unknown"

    def __init__(self, message: str, *, service: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.service = service
        self.status_code = status_code

    def details(self) -> dict[str, Any] | None:
        """Detalhes estruturados para o payload da exception (`None` = sem detalhes)"""
        return None


class InternalServiceValidationException(InternalServiceException):
    """Requisição rejeitada pelo serviço interno por parâmetro obrigatório ausente ou malformado"""

    http_status = 400
    error_type = "validation"


class InternalServiceNotFoundException(InternalServiceException):
    """Recurso não encontrado no serviço interno"""

    http_status = 404
    error_type = "not_found"


class InternalServiceTimeoutException(InternalServiceException):
    """Chamada ao serviço interno excedeu o timeout configurado no client"""

    http_status = 504
    error_type = "timeout"


class InternalServiceUnavailableException(InternalServiceException):
    """Falha do lado do serviço interno (rede ou 5xx) após as tentativas de retry"""

    http_status = 503
    error_type = "unavailable"


class InternalServiceUpstreamException(InternalServiceException):
    """Fallback para erro do serviço interno não mapeado -> status HTTP inesperado (ex.: 401/403/429)"""

    http_status = 502
    error_type = "upstream"


class LlmKeyException(Exception):
    """Exceção base de erro ao entregar ou registrar chaves de LLM"""

    http_status: int = 500
    error_type: str = "llm_key_error"

    def __init__(self, message: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds

    def details(self) -> dict[str, Any] | None:
        """Detalhes opcionais incluídos no corpo da resposta de erro"""
        return None


class LlmKeysNotConfiguredException(LlmKeyException):
    """Nenhuma chave configurada para o provedor/uso pedido"""

    http_status = 404
    error_type = "keys_not_configured"


class LlmKeysUnavailableException(LlmKeyException):
    """Há chaves configuradas, mas nenhuma disponível agora (em descanso ou inválidas)"""

    http_status = 503
    error_type = "keys_unavailable"

    def details(self) -> dict[str, Any] | None:
        if self.retry_after_seconds is None:
            return None
        return {"retry_after_seconds": self.retry_after_seconds}


class LlmKeyNotFoundException(LlmKeyException):
    """Identificador de chave desconhecido"""

    http_status = 404
    error_type = "key_not_found"
