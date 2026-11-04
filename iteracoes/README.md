# Iterações de specs

App local para **ver, analisar, editar e comparar versões** dos `.md` de
`specs/` sem risco de perder o ponto de partida. Só biblioteca padrão do
Python; roda no navegador, servido em `127.0.0.1`.

```bash
python -m iteracoes                    # sobe em http://127.0.0.1:8765/ e abre o navegador
python -m iteracoes --porta 8800       # outra porta
python -m iteracoes --sem-navegador    # só mostra o endereço
```

No Windows, dê dois cliques em `abrir-iteracoes.bat` na raiz do repositório.
Ctrl-C no terminal encerra o app.

O app **nunca roda o rvgen nem chama uma IA** (isso gera custo): ele só monta
o comando para você copiar.

## Onde ficam as versões

| versão | pasta | pode editar? |
|---|---|---|
| **Base** | `iteracoes/base/specs/` | não: somente leitura, o app nunca escreve ali ([BASE.md](base/BASE.md)) |
| **Ativa** | `specs/` | sim: é o que o `rvgen` lê por padrão; antes de gravar, o app faz backup |
| **it-NNN** | `iteracoes/it-NNN/specs/` | sim: cópia completa (inclui `upstream/`) |

Cada iteração tem um `iteracoes/it-NNN/iteracao.json` com `id`, `nome`,
`criada_em`, `origem` (`base`, `specs` ou `it-NNN`), `notas` e os
`experimentos` vinculados. Tudo isso fica versionado no git.

Para voltar ao ponto de partida, crie uma iteração nova a partir da base: a
base nunca muda.

## O que cada aba faz

- **Arquivos**: lista os `.md` da versão com o papel de cada um e o tamanho
  (caracteres e ~tokens = caracteres ÷ 4). Clique para abrir no editor;
  `Salvar` (ou Ctrl+S) grava. Na base o editor é só leitura.
  - *vai para a IA (prompt de sistema)*: `cpu.md`, `vhdl.md`, `riscv-rv32i.md`;
  - *vai para a IA (chamadas de teste)*: `testes.md`;
  - *só documentação, a IA não lê*: `constitution.md`, `plan.md`, `spec.md` e outros.
- **Comparar**: escolha A e B (qualquer versão); mostra quais arquivos mudaram,
  com `+`/`−` linhas, e o diff colorido do arquivo selecionado.
- **Análise**: checagens determinísticas (sem IA), tamanhos e a variação do
  prompt contra a base. Checagens:
  - erro: `cpu.md` não declara exatamente uma ISA (RV32I/RV32IM) e uma
    microarquitetura (single cycle, multicycle, pipeline) — o `rvgen` recusaria;
  - erro: bloco `entity cpu is ... end cpu;` ausente, porta das 9 obrigatórias
    ausente, ou entidade com `generic` (o `spec-riscv-test` recusa);
  - erro: `cpu.md`, `vhdl.md`, `riscv-rv32i.md` ou `testes.md` ausente ou vazio;
  - aviso: `-- REQ:` ou `FR-RV-` nos arquivos que vão para a IA (IDs sem definição);
  - info: `rvverify` citado nos arquivos que vão para a IA (o juiz do `rvgen` é o
    `spec-riscv-test`).
- **Prompt que a IA recebe**: o texto montado de verdade por
  `rvgen.contrato.texto_do_contrato` com as specs daquela versão (prompt de
  sistema) e o das chamadas de teste (contrato + `testes.md`). Só leitura.
- **Usar**: comandos prontos para rodar o `rvgen` com as specs da versão,
  em bash/WSL e em PowerShell; botão **Promover para specs/**; campo para
  **vincular um experimento** e ver o resultado da sessão mais recente
  (`experimentos/<nome>/.rvgen/sessao-*/resultado.json`: veredito, chamadas,
  tokens; numa sessão retomada, a soma de todas as execuções, como no
  `rvgen comparar`) e qual pasta de specs ela usou.

O botão **+ Nova iteração** copia a base, a ativa ou outra iteração, com nome
e notas (hipótese). Nome e notas podem ser editados depois no topo da página.

## Fluxo sugerido

1. **Criar** uma iteração a partir da base (ou da ativa) e escrever a hipótese nas notas.
2. **Editar** os `.md` na aba Arquivos.
3. Conferir a **Análise** (nenhum erro, tamanho do prompt) e o **diff** contra a base.
4. **Rodar o rvgen** com o comando da aba Usar (no terminal, Linux/WSL2 para o veredito):

   ```bash
   RVGEN_SPECS_DIR=iteracoes/it-002/specs python -m rvgen gerar it002_teste --max-chamadas 60
   ```

   ```powershell
   $env:RVGEN_SPECS_DIR='iteracoes/it-002/specs'; python -m rvgen gerar it002_teste --max-chamadas 60
   ```

5. **Vincular** o experimento (`it002_teste`) à iteração e comparar o resultado.
6. **Promover** para `specs/` se ficou melhor.

## Backups automáticos

- **Promover** `it-NNN`: antes de copiar, a `specs/` atual vira uma nova
  iteração `antes-de-promover-it-NNN`. Arquivos que só existem em `specs/` são
  mantidos.
- **Salvar na ativa** pelo app: antes de gravar, a `specs/` atual vira uma
  iteração `antes-de-editar-specs` (se ainda não houver uma igual).

## `RVGEN_SPECS_DIR`

O `rvgen` lê `cpu.md`, `vhdl.md`, `riscv-rv32i.md` e `testes.md` de
`specs/`. Com `RVGEN_SPECS_DIR` (caminho absoluto ou relativo à raiz do
repositório), lê da pasta indicada; o `rvgen gerar` mostra
`specs   : <pasta>` e registra a pasta no evento `inicio` da sessão
(`sessao.jsonl`, campo `specs`). Sem a variável, nada muda.

No PowerShell a variável fica valendo na janela até fechá-la; para voltar a
`specs/`: `Remove-Item Env:RVGEN_SPECS_DIR`.

## Segurança

O servidor escuta só em `127.0.0.1` e recusa `Host` que não seja local.
Pedidos que alteram arquivos (POST) exigem um token aleatório gerado na
partida e injetado na página (cabeçalho `X-Token`), `Origin` local e corpo
JSON de até 2 MB. Versões só podem ser `base`, `specs` ou `it-NNN`, e
arquivos só `.md` dentro da pasta de specs da versão (sem `..`, caminhos
absolutos ou `\`). O app só grava arquivos que já existem (ou recria um dos
quatro que o `rvgen` lê, se tiver sumido); arquivos novos você cria pelo
editor de sua preferência na pasta da iteração.

## Código

| arquivo | papel |
|---|---|
| `nucleo.py` | toda a lógica (`Repositorio(raiz)`): listar, criar, salvar, diff, analisar, promover, experimentos |
| `servidor.py` | `http.server` + API JSON |
| `app.html` | a página (HTML/CSS/JS inline, sem CDN; tema claro/escuro) |
| `__main__.py` | `python -m iteracoes` |
| `tests/` | testes (`python -m pytest iteracoes/tests`) |
