# Rodando o Projeto Localmente

Este repositório é Python (FastAPI). O fluxo local padrão: clonar, instalar dependências, preencher `.env` e rodar via `uvicorn` ou Docker.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python,fastapi,docker,googlecloud" height="48" alt="Rodando o Projeto — Python">
  </a>
</p>

## Possíveis Impedimentos

- **Python 3.14+ instalado localmente** (`pyproject.toml`, `requires-python = ">=3.14"`).
- **Chaves de API**, `GOOGLE_KEY_MAPS` precisa ter as APIs Places (New), Geocoding, Address Validation, Solar, Routes e Weather habilitadas no projeto do Google. O `.env.example` lista `GOOGLE_KEY_MAPS`/`GOOGLE_KEY_TRANSLATION`/`GOOGLE_CALENDAR_OAUTH_*` e as chaves de LLM (`GEMINI_API_KEY_1`, `GROQ_API_KEY_1`...) vazias — em produção elas vêm do [Infisical](https://infisical.com), localmente precisam ser preenchidas num `.env` próprio. As chaves de LLM são opcionais: sem elas `GET /v1/llm/keys` responde 404. As rotas `/v1/llm/*` exigem `Authorization: Bearer <REGISTRY_CONSUMER_TOKEN>`; sem a variável configurada respondem 503.
- **`api-auth` rodando** (ou apontado via `AUTH_BASE_URL`/`JWT_JWKS_URL`) só quando a autenticação e o Calendar forem usados; nenhuma capability atual grava em outro serviço.

## Instalação do Projeto

### Iniciando o repositório com o Github

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=github,vscode" height="48" alt="Frameworks">
  </a>
</p>

```Comandos para clonar o repositório
git clone https://github.com/Solierrr/google-registry.git
cd ./google-registry
code . -r
```

### Instalando dependências e rodando

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python" height="48" alt="Frameworks">
  </a>
</p>

```Comandos para instalação e start local
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

copy .env.example .env
:: preencher as chaves do .env antes de rodar

uvicorn app.main:app --reload
```

### Testes

```Comando de teste
pytest tests --cov=app
```

### Subindo via Docker

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=docker" height="48" alt="Docker">
  </a>
</p>

```Comando de build e run
docker build -t google-registry .
docker run --env-file .env -p 8000:8000 google-registry
```
