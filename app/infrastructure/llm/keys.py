import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.infrastructure.llm.providers import PROVIDER_BY_PREFIX

_NAME = re.compile(r"^(?P<prefix>[A-Z][A-Z0-9]*)_API_KEY(?:_?(?P<number>\d+))?$")


@dataclass(frozen=True)
class LlmKey:
    """Uma chave de LLM configurada"""

    provider: str
    key_id: str
    secret: str


def key_id_for(provider: str, secret: str) -> str:
    """Identificador estável e opaco da chave (não revela o segredo)"""
    return f"{provider}-{hashlib.sha256(secret.encode()).hexdigest()[:8]}"


def load_llm_keys(environ: Mapping[str, str]) -> list[LlmKey]:
    """Lê as chaves de LLM das variáveis de ambiente

    Variáveis vazias e provedores desconhecidos são ignorados; a mesma chave em duas variáveis conta uma vez.

    Args:
        environ: variáveis de ambiente

    Returns:
        As chaves, ordenadas por provedor e número da variável
    """
    found: list[tuple[str, int, str, str]] = []
    for name, value in environ.items():
        match = _NAME.match(name)
        secret = value.strip()
        if match is None or not secret:
            continue
        provider = PROVIDER_BY_PREFIX.get(match["prefix"])
        if provider is None:
            continue
        found.append((provider, int(match["number"] or 0), name, secret))

    keys: list[LlmKey] = []
    seen: set[tuple[str, str]] = set()
    for provider, _number, _name, secret in sorted(found):
        if (provider, secret) in seen:
            continue
        seen.add((provider, secret))
        keys.append(LlmKey(provider=provider, key_id=key_id_for(provider, secret), secret=secret))
    return keys
