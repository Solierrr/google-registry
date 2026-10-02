# google-registry

O `google-registry` é o serviço central de integração com APIs do Google da organização (Maps, Solar, Translate, chaves de LLM e, em breve, Calendar), consumido internamente pelos serviços da Solaria em vez de cada repositório configurar suas próprias credenciais.

<p>

[![License](https://img.shields.io/github/license/Solierrr/google-registry)](https://github.com/Solierrr/google-registry/blob/main/LICENSE)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Solierrr/google-registry)](https://github.com/Solierrr/google-registry/commits)
[![GitHub Issues](https://img.shields.io/github/issues/Solierrr/google-registry)](https://github.com/Solierrr/google-registry/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/Solierrr/google-registry)](https://github.com/Solierrr/google-registry/pulls)
[![GitHub Contributors](https://img.shields.io/github/contributors/Solierrr/google-registry)](https://github.com/Solierrr/google-registry/graphs/contributors)
[![Release](https://img.shields.io/github/v/release/Solierrr/google-registry)](https://github.com/Solierrr/google-registry/releases)

</p>

<div align="center">

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python,fastapi,googlecloud,docker" height="48" alt="Stack do Projeto">
  </a>
</p>

</div>

## Status

- **FastAPI**, arquitetura em camadas (`domain`/`application`/`infrastructure`/`api`), um módulo por capability.
- **Sem estado**, o serviço só chama o Google (ou lê chaves do ambiente) conforme os parâmetros e devolve o resultado; quem chamou grava onde precisar.
- **Capability `address`**, sugestão de endereço, detalhes por `place_id`, geocodificação (direta e reversa), validação e `resolve` (Places New, Geocoding e Address Validation).
- **Capability `solar`**, viabilidade solar de um telhado via Solar API, incluindo os dados do painel de referência.
- **Capability `i18n`**, detecção de idioma + tradução (Cloud Translation API) de campos de texto para os outros dois entre `en`/`es`/`pt`.
- **Capability `llm`**, corretor de chaves de modelos (Gemini, Groq): entrega uma chave em rodízio FIFO, aceita aviso de limite de uso/chave inválida e verifica a validade em segundo plano.
- **Capability `geo`**, fuso horário por coordenada, calculado localmente.
- **Autenticação**, JWT RS256 de usuário validado via JWKS do `api-auth` (`app/infrastructure/auth`); ainda não aplicado nos endpoints.
- **Observabilidade**, logging/tracing/metrics via OpenTelemetry.
- **Licença Apache 2.0**.

## Aprofunde-se no Projeto!

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [RUNNING.md](./RUNNING.md)

## Contribuindo

- {a confirmar}, este repositório ainda não possui `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` ou `SECURITY.md` — consulte os templates em [docs-warehouse](https://github.com/Solierrr/docs-warehouse) para criá-los.
