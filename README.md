# google-registry

O `google-registry` é, pelo nome do repositório e pelas chaves já scaffoldadas no `.env.example` (`GOOGLE_TRANSLATE_API_KEY`, `GOOGLE_MAPS_API_KEY`, `GOOGLE_CALENDAR_API_KEY`), provavelmente um serviço destinado a centralizar a integração com APIs do Google — Translate, Maps e Calendar — para que outros serviços da organização consumam essas capacidades por trás de um ponto único, em vez de cada repositório configurar suas próprias credenciais Google. **Essa descrição é uma inferência a partir do scaffold existente, não um fato confirmado em código**: o repositório ainda não possui nenhuma linha de lógica de aplicação. Não há arquivos `.py`, não há definição de rotas, não há cliente HTTP configurado para nenhuma das três APIs. O que existe hoje é só o esqueleto de containerização (`Dockerfile`) e o contrato de variáveis de ambiente esperado (`.env.example`).

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
    <img src="https://skills.syvixor.com/api/icons?i=python,googlecloud,docker" height="48" alt="Stack do Projeto">
  </a>
</p>

</div>

## Status

- **Scaffold de container**, existe um `Dockerfile` baseado em `python:latest` que expõe a porta `8000`, mas depende de um `requirements.txt` que ainda não foi criado — o build da imagem falha hoje, veja detalhes em [ARCHITECTURE.md](./ARCHITECTURE.md).
- **Contrato de variáveis de ambiente**, o `.env.example` já define as três chaves de API do Google esperadas pelo serviço, mesmo sem código que as consuma ainda.
- **Sem código-fonte Python**, nenhum arquivo `.py`, nenhum framework web escolhido, nenhum endpoint implementado. {a confirmar} qual framework (FastAPI, Flask, etc.) será usado.
- **Licença MIT** já definida em [LICENSE](./LICENSE), sob copyright da Solaria.

## Aprofunde-se no Projeto!

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [RUNNING.md](./RUNNING.md)

## Contribuindo

- {a confirmar}, este repositório ainda não possui `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` ou `SECURITY.md` — consulte os templates em [docs-warehouse](https://github.com/Solierrr/docs-warehouse) para criá-los quando o código-fonte começar a ser implementado.
