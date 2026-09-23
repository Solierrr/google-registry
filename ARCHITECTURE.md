# Arquitetura do Repositório

FastAPI, arquitetura em camadas por capability (`domain` -> `application` -> `infrastructure` -> `api`), igual em `solar` e `i18n`.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python,fastapi,googlecloud,docker" height="48" alt="Stack do Projeto">
  </a>
</p>

## Camadas

- **`app/domain/<capability>/ports.py`**, contrato (`Protocol`) que a capability espera do provedor Google — nenhum detalhe de HTTP/formato de payload aqui.
- **`app/application/<capability>/service.py`**, orquestra o port da capability e, quando aplicável, o client de `api-core` para gravar o resultado.
- **`app/infrastructure/google/<capability>/adapter.py`**, único lugar que conhece o formato de request/response da API Google real, sobre o `GoogleHttpClient` (`app/infrastructure/http`) compartilhado (timeout, retry/backoff, observabilidade).
- **`app/infrastructure/solier/{auth,persistence}/*_client.py`**, clientes dos serviços internos Solier (`api-core`/`api-auth`), sobre o `InternalHttpClient` compartilhado, mesma estrutura do `GoogleHttpClient`.
- **`app/api/routers/<capability>.py`**, endpoints FastAPI (`/v1/<capability>/...`), monta o service via `Depends` a partir dos clients criados no lifespan (`app/api/dependencies.py`).
- **`app/schemas/<capability>.py`**, DTOs públicos (Pydantic) do router.

## Capabilities

- **`solar`**, viabilidade solar de um telhado (`buildingInsights:findClosest`); com `unit_id`, grava o perfil solar em `api-core`.
- **`i18n`**, chamado por `api-core` logo após inserir/atualizar um registro cujos campos de texto entram no escopo de tradução automática; detecta o idioma de origem (Cloud Translation API, `detect`) e traduz pros outros dois dos três idiomas suportados (`en`/`es`/`pt`), gravando o resultado numa tabela genérica de traduções em `api-core`.

## Observabilidade e autenticação

- **OpenTelemetry** (`app/infrastructure/observability`), logging (console + OTLP), tracing (span por chamada Google/interna) e métricas (contador + histograma de duração, por capability/serviço).
- **JWT RS256** (`app/infrastructure/auth`), valida o token de usuário emitido pelo `api-auth` via JWKS — usado pelos endpoints que expõem operações do usuário final (nenhum endpoint hoje declara essa dependency; adicionar via `Depends(require_authenticated_user)` quando fizer sentido).

## Containerização

- `Dockerfile` instala a partir de `pyproject.toml` (`pip install .`) e sobe `uvicorn app.main:app` na porta `8000`.

```Tree do Repositório
├── app/
│   ├── api/            # routers + dependencies FastAPI
│   ├── application/    # services por capability
│   ├── domain/          # ports (contratos) por capability
│   ├── exceptions/       # hierarquia de exceptions + handlers
│   ├── infrastructure/
│   │   ├── auth/         # JWT/JWKS do api-auth
│   │   ├── google/       # adapters por capability
│   │   ├── http/         # clients HTTP compartilhados (Google/interno)
│   │   ├── observability/ # logging/tracing/metrics OTEL
│   │   └── solier/       # clients dos serviços internos Solier
│   ├── schemas/          # DTOs por capability
│   ├── config.py
│   └── main.py
├── tests/
├── Dockerfile
├── pyproject.toml
└── sonar-project.properties
```
