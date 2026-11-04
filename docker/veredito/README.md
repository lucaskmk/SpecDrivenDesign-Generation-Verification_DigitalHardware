# `rvgen-veredito`: ambiente reprodutível do veredito do rvgen

Imagem com tudo o que o `rvgen` precisa para julgar uma CPU com o
`spec-riscv-test` (o juiz oficial) sem instalar nada no host:

- GHDL 2.0.0, cocotb 2.0.0 e Python 3.11.2 da imagem das aulas,
  `rafaelcorsi/pl-descomp-cocotb`, **fixa por digest** (`sha256:8dc17254…`, o
  `:latest` publicado em 2025-09-29; o mesmo de `docker/spechdl-toolchain`);
- `gcc-riscv64-unknown-elf` 12.2.0 (`12.2.0-14+deb12u1+11+b2`) e
  `binutils-riscv64-unknown-elf` 2.40 (`2.40-2+4+b1`) do Debian 12, **com versão
  fixa** no `apt-get`, que compilam os programas de teste;
- o [riscv-tests](https://github.com/riscv-software-src/riscv-tests) oficial em
  `/opt/riscv-tests`, **fixo no commit**
  `3df703cd52d5f0d8224e3c50bf03c6cb70efff98` (o commit fica gravado em
  `/opt/riscv-tests.versao`);
- um wrapper `/usr/local/bin/spec-riscv-test` que roda
  `python3 -m spec_riscv_test.cli` direto do código do repositório montado
  (`PYTHONPATH=/repo/spec-riscv-test`), ou seja, o juiz é sempre o da pasta
  `spec-riscv-test/` do checkout, cujo hash o `rvgen` confere.

Variáveis já definidas na imagem: `RVGEN_SPEC_RISCV_TEST=/usr/local/bin/spec-riscv-test`,
`RVGEN_RISCV_TESTS=/opt/riscv-tests` e `PYTHONDONTWRITEBYTECODE=1`. O diretório
de trabalho é `/repo`.

A imagem **não contém o repositório nem segredos**: o repositório entra montado
em `/repo` a cada `docker run`, e o `.env` da raiz (com `OPENROUTER_API_KEY`
etc.) é lido pelo `rvgen` a partir dessa montagem. Nunca copie a chave para a
imagem (nada de `COPY .env` nem `ENV OPENROUTER_API_KEY=...`).

## Build

Da raiz do repositório:

```
docker build -t rvgen-veredito docker/veredito
```

Com a base, o compilador e o `riscv-tests` fixos, o veredito sai igual em
qualquer máquina que consiga montar a imagem. Só `git` e `ca-certificates`,
que servem para baixar o `riscv-tests` e não entram no veredito, ficam sem
versão fixa. Se o espelho do Debian deixar de ter a versão fixada do
compilador, o build falha em vez de trocar o compilador em silêncio.

Para trocar uma peça (só se o contrato mudar), use `--build-arg`:
`RISCV_TESTS_COMMIT=<sha>` (o build falha se o commit não existir),
`BASE_IMAGE=<imagem@sha256:...>`, `RISCV_GCC_VERSION=<versão>` ou
`RISCV_BINUTILS_VERSION=<versão>`.

## Montar o repositório

Todos os comandos abaixo rodam da raiz do repositório.

No **Git Bash** do Windows, o caminho do `-v` precisa de
`MSYS_NO_PATHCONV=1`; sem isso o MSYS reescreve `/repo` como um caminho do
Windows e a montagem sai errada. Defina uma vez por terminal:

```bash
export MSYS_NO_PATHCONV=1
REPO="$(pwd -W)"          # caminho Windows do repositório (C:/Users/...)
```

No **PowerShell** basta `${PWD}`. No Linux/macOS, use `"$(pwd)"` e, para os
arquivos gerados não ficarem com dono `root`, acrescente
`--user "$(id -u):$(id -g)" -e HOME=/tmp` ao `docker run`.

## Rodar o juiz no gabarito

Espera-se `40/40` e `"status": "passed"` no `report.json` da pasta passada em
`--out` (nos exemplos, `/tmp/o`, dentro do container; ver abaixo como
guardá-lo no host).

Git Bash:

```bash
docker run --rm -v "$REPO:/repo" rvgen-veredito \
  spec-riscv-test --cpu cpus/rv32i_gabarito --riscv-tests /opt/riscv-tests --isa rv32i --out /tmp/o
```

PowerShell:

```powershell
docker run --rm -v "${PWD}:/repo" rvgen-veredito `
  spec-riscv-test --cpu cpus/rv32i_gabarito --riscv-tests /opt/riscv-tests --isa rv32i --out /tmp/o
```

Com `--out /tmp/o` o relatório fica só dentro do container; para guardá-lo no
host, troque por uma pasta do repositório (por exemplo `--out out/gabarito`).

## Conferir o ambiente do rvgen

```bash
docker run --rm -v "$REPO:/repo" rvgen-veredito python3 -m rvgen preparar --verificar --executor local
```

```powershell
docker run --rm -v "${PWD}:/repo" rvgen-veredito python3 -m rvgen preparar --verificar --executor local
```

A linha `executor do spec-riscv-test: local` tem de aparecer como `ok`.

## Gerar uma CPU

O `rvgen gerar <nome>` grava em `experimentos/<nome>` (dentro do repositório
montado, portanto no host). Use `-it` para ver o progresso e poder
interromper com Ctrl+C; `--max-chamadas N` limita o número de chamadas ao
modelo.

Git Bash:

```bash
docker run --rm -it -v "$REPO:/repo" rvgen-veredito \
  python3 -m rvgen gerar <nome> --executor local --max-chamadas N
```

PowerShell:

```powershell
docker run --rm -it -v "${PWD}:/repo" rvgen-veredito `
  python3 -m rvgen gerar <nome> --executor local --max-chamadas N
```

O provedor e a chave vêm do `.env` da raiz. Para usar um Ollama que roda no
host, passe `-e OLLAMA_HOST=http://host.docker.internal:11434` (no Linux,
acrescente também `--add-host=host.docker.internal:host-gateway`).

## Retomar uma sessão interrompida

O id da sessão aparece na saída do `gerar` e no nome da pasta
`experimentos/<nome>/.rvgen/sessao-<id>`; pode ser passado com ou sem o
prefixo `sessao-`.

Git Bash:

```bash
docker run --rm -it -v "$REPO:/repo" rvgen-veredito \
  python3 -m rvgen retomar <nome> <sessao> --executor local --max-chamadas N
```

PowerShell:

```powershell
docker run --rm -it -v "${PWD}:/repo" rvgen-veredito `
  python3 -m rvgen retomar <nome> <sessao> --executor local --max-chamadas N
```

Como no `gerar`, um `<nome>` sem diretório vira `experimentos/<nome>`.
`--max-casos-teste` e `--max-casos-internos` não informados são herdados da
sessão original, desde que ela tenha sido criada depois do commit `f59dcc6`,
que passou a gravar esses limites no evento `inicio` do `sessao.jsonl`. Numa
sessão mais antiga o `retomar` volta ao padrão (32 e 8); passe os valores de
novo (por exemplo `--max-casos-teste 4` para retomar a sessão do
`luna6_prof_3`). `--max-chamadas` e `--max-tokens` valem para esta execução e
precisam ser passados de novo se você quiser limitá-la.
