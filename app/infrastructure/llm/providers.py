from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """Como falar com um provedor de LLM"""

    name: str
    base_url: str
    auth_header_name: str
    auth_value_prefix: str
    probe_path: str
    supports_embedding: bool

    def auth_value(self, api_key: str) -> str:
        """Valor completo do cabeçalho de autenticação para a chave"""
        return f"{self.auth_value_prefix}{api_key}"


PROVIDERS: dict[str, Provider] = {
    "gemini": Provider(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        auth_header_name="x-goog-api-key",
        auth_value_prefix="",
        probe_path="/models?pageSize=1",
        supports_embedding=True,
    ),
    "groq": Provider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        auth_header_name="Authorization",
        auth_value_prefix="Bearer ",
        probe_path="/models",
        supports_embedding=False,
    ),
}

# Nome da variável de ambiente (prefixo antes de `_API_KEY`) -> provedor
PROVIDER_BY_PREFIX: dict[str, str] = {"GEMINI": "gemini", "GOOGLE": "gemini", "GROQ": "groq"}
