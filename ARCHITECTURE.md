# Arquitetura do Repositório

O `google-registry` ainda não possui arquitetura de aplicação para descrever, porque não há código-fonte Python no repositório neste momento. O que existe é somente um scaffold mínimo de containerização e o contrato de variáveis de ambiente esperado para o serviço, inferido a partir das três chaves de API já declaradas no `.env.example`. Este documento registra o estado real do repositório hoje, incluindo uma inconsistência entre `Dockerfile` e o restante do repositório, em vez de descrever uma arquitetura em camadas que ainda não foi implementada.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python,googlecloud,docker" height="48" alt="Stack do Projeto">
  </a>
</p>

- **Nenhuma arquitetura de aplicação implementada**, não há camadas, módulos, controllers ou clientes de API — apenas o scaffold de container e o contrato de `.env`.
- **Inconsistência no `Dockerfile`**, o arquivo executa `COPY requirements.txt .` e `RUN pip install --no-cache-dir -r requirements.txt` (linhas 5 e 7), mas nenhum `requirements.txt` existe no repositório — o build da imagem falha na etapa de instalação de dependências até que o arquivo seja criado.
- **`FROM python:latest` sem estágio de build**, diferente do padrão multi-stage descrito no `DEPLOYMENT.md` de [docs-warehouse](https://github.com/Solierrr/docs-warehouse) para outras stacks, o `Dockerfile` de Python da organização roda direto sobre a imagem base, sem separar build e runtime — isso está alinhado ao template de referência, mas ainda depende do `requirements.txt` existir para funcionar.
- **Propósito provável, não confirmado**, o nome do repositório e as chaves `GOOGLE_TRANSLATE_API_KEY`, `GOOGLE_MAPS_API_KEY` e `GOOGLE_CALENDAR_API_KEY` sugerem um serviço central de integração com APIs do Google, mas nada no código confirma essa hipótese hoje.

## O que precisa ser implementado

- `requirements.txt` na raiz do repositório, com as dependências mínimas para o `Dockerfile` conseguir buildar.
- Código-fonte Python da aplicação (framework web, entrypoint, rotas) — {a confirmar} qual framework será adotado.
- Lógica de integração com as três APIs do Google referenciadas no `.env.example`, hoje apenas declaradas como variáveis vazias.
- Documentação de contribuição (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`), ausentes no repositório.

```Tree do Repositório
├── .dockerignore
├── .editorconfig
├── .env.example
├── Dockerfile
├── LICENSE
├── README.md
├── ARCHITECTURE.md
└── RUNNING.md
```
