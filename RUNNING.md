# Rodando o Projeto Localmente

Este repositório é Python (FastAPI). O fluxo local padrão: clonar, instalar dependências, preencher `.env` e rodar via `uvicorn` ou Docker.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python,fastapi,docker,googlecloud" height="48" alt="Rodando o Projeto — Python">
  </a>
</p>

## Possíveis Impedimentos

- **Python 3.14+ instalado localmente** (`pyproject.toml`, `requires-python = ">=3.14"`).
- **Chaves de API do Google**, o `.env.example` lista `GOOGLE_KEY_MAPS`/`GOOGLE_KEY_TRANSLATION`/`GOOGLE_CALENDAR_OAUTH_*` vazias — em produção elas vêm do [Infisical](https://infisical.com), localmente precisam ser preenchidas num `.env` próprio.
- **`api-core` e `api-auth` rodando** (ou apontados via `PERSISTENCE_BASE_URL`/`AUTH_BASE_URL`), já que várias capabilities gravam resultado em `api-core` e a autenticação valida contra o JWKS do `api-auth`.

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
