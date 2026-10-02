# Arquitetura do Repositório

FastAPI, arquitetura em camadas por capability (`domain` -> `application` -> `infrastructure` -> `api`), igual em `solar` e `i18n`.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python,fastapi,googlecloud,docker" height="48" alt="Stack do Projeto">
  </a>
</p>

## Camadas

- **`app/domain/<capability>/ports.py`**, contrato (`Protocol`) que a capability espera do provedor Google — nenhum detalhe de HTTP/formato de payload aqui.
- **`app/application/<capability>/service.py`**, orquestra os ports da capability. Não grava nada em outros serviços: devolve o resultado a quem chamou.
- **`app/infrastructure/google/<capability>/adapter.py`**, único lugar que conhece o formato de request/response da API Google real, sobre o `GoogleHttpClient` (`app/infrastructure/http`) compartilhado (timeout, retry/backoff, observabilidade).
- **`app/infrastructure/solier/auth/*_client.py`**, cliente do `api-auth` (tokens do Calendar, ainda sem uso), sobre o `InternalHttpClient` compartilhado, mesma estrutura do `GoogleHttpClient`.
- **`app/api/routers/<capability>.py`**, endpoints FastAPI (`/v1/<capability>/...`), monta o service via `Depends` a partir dos clients criados no lifespan (`app/api/dependencies.py`).
- **`app/schemas/<capability>.py`**, DTOs públicos (Pydantic) do router.

## Capabilities

- **`address`**, `/v1/address/{suggestions,places/{place_id},geocode,reverse-geocode,validate,resolve}`; três adapters (Places New, Geocoding, Address Validation) atrás de um `AddressService`. `resolve` junta busca e validação; se a validação falhar, o endereço volta com `validation: null`.
- **`solar`**, `/v1/solar/roof-viability` (`buildingInsights:findClosest`), com os dados do painel de referência do Google.
- **`routes`**, `POST /v1/routes/compute` (`directions/v2:computeRoutes`); `DRIVE` com `TRAFFIC_AWARE` e `departure_at` opcionais, `WALK`, `avoid_tolls`/`avoid_highways` só em `DRIVE`, até 3 rotas (`duration_seconds`, `distance_meters`, `encoded_polyline`); 404 se o Google não achar rota.
- **`weather`**, `GET /v1/weather/hourly` (`forecast/hours:lookup`); devolve a hora que contém `at` (padrão: agora) percorrendo as páginas do Google; `at` precisa estar entre 1 hora atrás e 239 horas à frente (422 fora disso); 404 se o Google não cobrir o instante.
- **`i18n`**, `/v1/i18n/translate`; detecta o idioma de origem (Cloud Translation API, `detect`) e traduz os campos para os outros dois dos três idiomas suportados (`en`/`es`/`pt`), um lote por idioma de destino.
- **`llm`**, `/v1/llm/{keys,keys/{key_id}/report,providers}`; não chama o Google: lê do ambiente as chaves `<PROVEDOR>_API_KEY_<N>` (Gemini e Groq), exige `Authorization: Bearer <REGISTRY_CONSUMER_TOKEN>` (`infrastructure/auth/consumer_token.py`, 401 sem token, 503 se o token não estiver configurado), mantém uma fila FIFO (`application/llm/key_pool.py`) e verifica a validade das chaves em segundo plano (`infrastructure/llm/probe.py`). Estado em memória, uma réplica.
- **`geo`**, `/v1/geo/timezone`; fuso por coordenada via `tzfpy`, sem API externa.

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
│   │   ├── geo/          # fuso horário local
│   │   ├── llm/          # chaves, provedores e verificação de chaves de LLM
│   │   └── solier/       # cliente do api-auth
│   ├── schemas/          # DTOs por capability
│   ├── config.py
│   └── main.py
├── tests/
├── Dockerfile
├── pyproject.toml
└── sonar-project.properties
```
