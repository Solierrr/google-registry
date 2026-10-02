"""Assinatura do `state` do fluxo OAuth do Calendar

O `state` liga o callback ao técnico que iniciou o consentimento e expira em poucos minutos.
Nada é guardado no servidor: o valor é autoverificável (HMAC-SHA256)
"""

import base64
import hashlib
import hmac
import time
from collections.abc import Callable

_DEFAULT_TTL_SECONDS = 600


class InvalidStateError(ValueError):
    """`state` adulterado, malformado ou expirado"""


class CalendarStateSigner:
    """Gera e valida o `state`, no formato `base64url(<technician_id>.<expiração>).<hmac>`"""

    def __init__(
        self, secret: str, *, ttl_seconds: int = _DEFAULT_TTL_SECONDS, clock: Callable[[], float] = time.time
    ) -> None:
        self._secret = secret.encode()
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def sign(self, technician_id: str) -> str:
        """Assina um `state` para o técnico, válido por `ttl_seconds`

        Args:
            technician_id: técnico que inicia o consentimento

        Returns:
            O `state`, seguro para ir na URL
        """
        expires_at = int(self._clock()) + self._ttl_seconds
        payload = base64.urlsafe_b64encode(f"{technician_id}.{expires_at}".encode()).decode().rstrip("=")
        return f"{payload}.{self._mac(payload)}"

    def verify(self, state: str) -> str:
        """Valida o `state` e devolve o técnico que o originou

        Args:
            state: valor recebido no callback

        Returns:
            O identificador do técnico

        Raises:
            InvalidStateError: assinatura inválida, formato inesperado ou `state` expirado
        """
        payload, separator, signature = state.rpartition(".")
        if not separator or not hmac.compare_digest(self._mac(payload), signature):
            raise InvalidStateError("state inválido")
        try:
            decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
            technician_id, _, expires_at = decoded.rpartition(".")
            expired = int(expires_at) < self._clock()
        except ValueError as exc:
            raise InvalidStateError("state inválido") from exc
        if not technician_id or expired:
            raise InvalidStateError("state expirado" if technician_id else "state inválido")
        return technician_id

    def _mac(self, payload: str) -> str:
        digest = hmac.new(self._secret, payload.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")
