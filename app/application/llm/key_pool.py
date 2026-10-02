import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.exceptions import (
    LlmKeyNotFoundException,
    LlmKeysNotConfiguredException,
    LlmKeysUnavailableException,
)
from app.infrastructure.llm.keys import LlmKey
from app.infrastructure.llm.providers import PROVIDERS
from app.schemas.llm import KeyState, KeyStatus, Outcome, ProvidersResponse, ProviderState

DEFAULT_COOLDOWN_SECONDS = 60
MAX_COOLDOWN_SECONDS = 86400


@dataclass
class _Entry:
    key: LlmKey
    status: KeyStatus = "available"
    available_at: float | None = None
    last_checked_at: float | None = None


@dataclass
class KeyPool:
    """Estado em memória das chaves de LLM (uma réplica do serviço)"""

    keys: list[LlmKey]
    clock: Callable[[], float]
    default_cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    _entries: dict[str, _Entry] = field(init=False, default_factory=dict)
    _queue: deque[str] = field(init=False, default_factory=deque)

    def __post_init__(self) -> None:
        for key in self.keys:
            self._entries[key.key_id] = _Entry(key)
            self._queue.append(key.key_id)

    def lease(self, *, provider: str | None = None, embedding: bool = False, exclude: set[str] | None = None) -> LlmKey:
        """Entrega a primeira chave elegível da fila e a recoloca no fim

        Args:
            provider: restringe a um provedor (omitido: qualquer um)
            embedding: só provedores que oferecem embeddings
            exclude: identificadores de chaves que o consumidor acabou de ver falhar

        Returns:
            A chave a usar

        Raises:
            LlmKeysNotConfiguredException: nenhuma chave configurada para o provedor/uso pedido
            LlmKeysUnavailableException: há chaves, mas nenhuma disponível agora
        """
        self._recover()
        excluded = exclude or set()

        for key_id in self._queue:
            entry = self._entries[key_id]
            if self._eligible(entry.key, provider, embedding) and key_id not in excluded:
                self._queue.remove(key_id)
                self._queue.append(key_id)
                return entry.key

        candidates = [e for e in self._entries.values() if self._eligible(e.key, provider, embedding)]
        if not candidates:
            raise LlmKeysNotConfiguredException(self._not_configured_message(provider, embedding))
        raise LlmKeysUnavailableException(
            "Nenhuma chave disponível no momento", retry_after_seconds=self._retry_after(candidates)
        )

    def report(self, key_id: str, outcome: Outcome, retry_after_seconds: int | None = None) -> None:
        """Registra o resultado do uso de uma chave (idempotente)

        Args:
            key_id: identificador da chave
            outcome: ok, rate_limited (limite de uso atingido) ou invalid (chave recusada)
            retry_after_seconds: em rate_limited, quanto esperar antes de reutilizar a chave

        Raises:
            LlmKeyNotFoundException: identificador desconhecido
        """
        entry = self._entry(key_id)
        if outcome == "rate_limited":
            seconds = min(retry_after_seconds or self.default_cooldown_seconds, MAX_COOLDOWN_SECONDS)
            available_at = self.clock() + seconds
            if entry.status == "cooling_down" and entry.available_at is not None:
                available_at = max(available_at, entry.available_at)
            if entry.status != "invalid":
                self._remove_from_queue(key_id)
                entry.status = "cooling_down"
                entry.available_at = available_at
        elif outcome == "invalid":
            self._remove_from_queue(key_id)
            entry.status = "invalid"
            entry.available_at = None

    def set_probe_result(self, key_id: str, valid: bool) -> None:
        """Registra o resultado da verificação de validade da chave

        Args:
            key_id: identificador da chave
            valid: se o provedor aceitou a chave

        Raises:
            LlmKeyNotFoundException: identificador desconhecido
        """
        entry = self._entry(key_id)
        if not valid:
            self._remove_from_queue(key_id)
            entry.status = "invalid"
            entry.available_at = None
            return
        entry.last_checked_at = self.clock()
        if entry.status == "invalid":
            entry.status = "available"
            self._queue.append(key_id)

    def snapshot(self) -> ProvidersResponse:
        """Estado de todas as chaves, agrupado por provedor, sem os segredos"""
        self._recover()
        grouped: dict[str, list[KeyState]] = {}
        for entry in self._entries.values():
            grouped.setdefault(entry.key.provider, []).append(
                KeyState(
                    key_id=entry.key.key_id,
                    status=entry.status,
                    available_at=_to_datetime(entry.available_at),
                    last_checked_at=_to_datetime(entry.last_checked_at),
                )
            )
        return ProvidersResponse(providers=[ProviderState(provider=p, keys=k) for p, k in sorted(grouped.items())])

    def _recover(self) -> None:
        now = self.clock()
        for key_id, entry in self._entries.items():
            if entry.status == "cooling_down" and entry.available_at is not None and entry.available_at <= now:
                entry.status = "available"
                entry.available_at = None
                self._queue.append(key_id)

    def _entry(self, key_id: str) -> _Entry:
        entry = self._entries.get(key_id)
        if entry is None:
            raise LlmKeyNotFoundException("Chave desconhecida")
        return entry

    def _remove_from_queue(self, key_id: str) -> None:
        if key_id in self._queue:
            self._queue.remove(key_id)

    @staticmethod
    def _eligible(key: LlmKey, provider: str | None, embedding: bool) -> bool:
        if provider is not None and key.provider != provider:
            return False
        return not embedding or PROVIDERS[key.provider].supports_embedding

    def _retry_after(self, candidates: list[_Entry]) -> int | None:
        """Segundos até a primeira chave em descanso voltar (nulo se nenhuma volta sozinha)"""
        now = self.clock()
        waits = [e.available_at - now for e in candidates if e.status == "cooling_down" and e.available_at is not None]
        return max(1, math.ceil(min(waits))) if waits else None

    @staticmethod
    def _not_configured_message(provider: str | None, embedding: bool) -> str:
        if provider is not None:
            return f"Nenhuma chave configurada para o provedor {provider}"
        if embedding:
            return "Nenhuma chave configurada para um provedor com embeddings"
        return "Nenhuma chave de LLM configurada"


def _to_datetime(timestamp: float | None) -> datetime | None:
    return datetime.fromtimestamp(timestamp, tz=UTC) if timestamp is not None else None
