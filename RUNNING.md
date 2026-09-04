# Rodando o Projeto Localmente

Este repositório é Python, mas hoje **não é possível rodar a aplicação localmente nem via container**, porque o código-fonte ainda não foi escrito e o `Dockerfile` depende de um `requirements.txt` que não existe no repositório. Este documento descreve o processo esperado (baseado no padrão Python da organização) e marca explicitamente onde ele quebra hoje, em vez de omitir o impedimento.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python,docker,googlecloud" height="48" alt="Rodando o Projeto — Python">
  </a>
</p>

## Possíveis Impedimentos

- **`requirements.txt` inexistente (impedimento confirmado)**, o `Dockerfile` referencia `COPY requirements.txt .` e `RUN pip install --no-cache-dir -r requirements.txt`, mas esse arquivo não existe na raiz do repositório. Tanto `docker build` quanto o passo equivalente local (`pip install -r requirements.txt`) falham hoje até que o arquivo seja criado.
- **Nenhum código-fonte Python**, não há `main.py`, `app.py` ou qualquer módulo de entrypoint — mesmo instalando dependências manualmente, não há o que rodar com `uvicorn` ou equivalente. {a confirmar} qual será o entrypoint e o framework web.
- **Python 3.x instalado localmente**, a mesma versão usada no `Dockerfile` (`python:latest`, sem pin de versão — {a confirmar} qual versão será fixada) — rodar fora do container exige essa versão instalada na máquina.
- **Chaves de API do Google**, o `.env.example` já lista `GOOGLE_TRANSLATE_API_KEY`, `GOOGLE_MAPS_API_KEY` e `GOOGLE_CALENDAR_API_KEY` vazias — mesmo quando o código existir, rodar localmente vai exigir preencher essas chaves em um `.env` próprio, já que em produção elas viriam do [Infisical](https://infisical.com) conforme o manifesto do [Infra-gitops](https://github.com/Solierrr/infra-gitops).

## Instalação do Projeto

### Iniciando o repositório com o Github

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=github,vscode" height="48" alt="Frameworks">
  </a>
</p>

Clone o repositório e abra no VS Code.

```Comandos para clonar o repositório
git clone https://github.com/Solierrr/google-registry.git
cd ./google-registry
code . -r
```

### Instalando dependências necessárias para rodar o projeto localmente

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=python" height="48" alt="Frameworks">
  </a>
</p>

Crie um ambiente virtual antes de instalar as dependências, para não poluir o Python global da máquina. **O passo abaixo falha hoje** na etapa `pip install -r requirements.txt`, porque o arquivo `requirements.txt` ainda não existe neste repositório — ele precisa ser criado antes que este fluxo funcione.

```Comandos para instalação de dependências
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Depois de resolver o `requirements.txt`, o comando de start da aplicação também é um impedimento em aberto: não há entrypoint Python no repositório (`main.py`, `app.py` ou equivalente) para apontar um comando como `uvicorn main:app --reload`. {a confirmar} assim que o código-fonte e o `Dockerfile` (`CMD`/`ENTRYPOINT`) definirem o módulo correto.

### Subindo via Docker

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=docker" height="48" alt="Docker">
  </a>
</p>

O build via Docker também falha hoje, pelo mesmo motivo — `COPY requirements.txt .` não encontra o arquivo na raiz do repositório.

```Comando de build (falha hoje)
docker build -t google-registry .
```
