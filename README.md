# google-registry

O `google-registry` é o serviço central de integração com APIs do Google da organização (Solar, Maps, Translate, Calendar), consumido internamente por `api-core`/`api-auth` em vez de cada repositório configurar suas próprias credenciais Google.

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
- **Capability `solar`**, viabilidade solar de um telhado via Solar API do Google, com gravação opcional do perfil em `api-core`.
- **Capability `i18n`**, detecção de idioma + tradução automática (Cloud Translation API) de campos de texto inseridos em `api-core`, gravada de volta lá.
- **Autenticação**, JWT RS256 de usuário validado via JWKS do `api-auth` (`app/infrastructure/auth`).
- **Observabilidade**, logging/tracing/metrics via OpenTelemetry.
- **Licença MIT**, sob copyright da Solaria.

## Aprofunde-se no Projeto!

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [RUNNING.md](./RUNNING.md)

## Contribuindo

- {a confirmar}, este repositório ainda não possui `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` ou `SECURITY.md` — consulte os templates em [docs-warehouse](https://github.com/Solierrr/docs-warehouse) para criá-los.
