# Trilha A (SpecHDL genérico) — contexto e o que ficou faltando

O projeto original, antes de a trilha RISC-V virar o foco. **Nada aqui foi
alterado pela trilha B** — este documento existe para registrar onde a trilha A
parou e o que falta, para quem retomar não precisar arqueologar.

Verificado por inspeção do repositório em 2026-09-06, não pela lista de
checkboxes (que estava desatualizada em três pontos — ver seção 4).

---

## 1. O contexto: o que a trilha A se propõe a ser

Um pipeline *spec-driven* para design de hardware digital. A ideia central é que
o aluno **não escreve enunciado em texto livre**: ele preenche um formulário web
local (Streamlit) com perguntas true/false e campos técnicos — largura de
palavra, número de estágios de pipeline, presença de cache. Ao submeter, o app
grava `rubrica.md` e o pipeline roda sozinho até o relatório final, **sem pedir
mais nenhuma decisão** (NFR-01).

As sete fases:

| Fase | O quê | Saída |
|---|---|---|
| 0 | Setup do ambiente | — |
| 1 | Ingestão da rubrica | `rubrica.md` → `spec.json` (EARS) |
| 2 | Decomposição arquitetural | `architecture.json` |
| 3 | Geração de VHDL + testbench cocotb | `outputs/<bloco>/` |
| 4 | Verificação no GHDL | `block_result.json` |
| 5 | Análise PPA (Yosys) | campo `ppa` |
| 6 | Relatório final | rastreabilidade requisito → bloco → código → teste |
| 7 | CLI `spechdl web` | ponto de entrada único |

Documentos: [`specs/constitution.md`](../specs/constitution.md),
[`specs/spec.md`](../specs/spec.md) (FR-01..FR-15, NFR-01..NFR-04),
[`specs/plan.md`](../specs/plan.md), [`specs/tasks.md`](../specs/tasks.md).

---

## 2. O que existe de fato hoje

A trilha A inteira mora em `legado/` desde a ADR-013 — os caminhos abaixo são
os de hoje, não os da raiz do repositório.

```
legado/src/spechdl/
├── __init__.py                    0 linhas
├── ingestion/
│   ├── __init__.py                0 linhas
│   ├── schema.py                328 linhas   ← schema da rubrica + validação cruzada
│   └── web_form.py              218 linhas   ← formulário Streamlit
├── architecture/__init__.py       0 linhas   ← vazio
├── codegen/__init__.py            0 linhas   ← vazio
├── verification/__init__.py       0 linhas   ← vazio
├── ppa/__init__.py                0 linhas   ← vazio
└── report/__init__.py             0 linhas   ← vazio

legado/tests/
└── __init__.py                    0 linhas   ← nenhum teste da trilha A existe

legado/templates/rubrica.md        ← schema da rubrica em markdown
legado/scripts/llm_playground.py
legado/.streamlit/config.toml
legado/abrir_formulario.bat        ← assume um .venv dentro de legado/
legado/ula32_sol/, legado/ula32_terra/, legado/toolchain_smoketest/
```

**546 linhas de código real, todas na fase 1.** As fases 2 a 6 são pacotes
vazios; a fase 7 não começou.

### O que funciona

- **O formulário roda.** `abrir_formulario.bat` ou `streamlit run` direto.
- **A validação cruzada existe e é usada.** `schema.py::validate_cross_fields`
  é chamada em `web_form.py:164` e o botão Submeter fica desabilitado enquanto
  houver erro (`st.button("Submeter", disabled=bool(errors))`). Isso é FR-03,
  e está mais adiantado do que o checkbox T1.3 sugere.
- **A submissão grava `rubrica.md`.** É o contrato de entrada da fase 2.

---

## 3. Um achado que vale registrar: o parser da fase 1 sumiu

Existe `legado/src/spechdl/ingestion/__pycache__/parser.cpython-312.pyc` — um bytecode
compilado — mas **não existe `parser.py` no fonte**, e ele **nunca foi commitado**:

```
git log --all --oneline -- legado/src/spechdl/ingestion/parser.py
→ (vazio)
```

E existe `outputs/spec.json`, com requisitos EARS já extraídos:

```json
{ "requirements": [
    { "id": "FR-01", "type": "functional",
      "text": "THE SYSTEM SHALL use Largura da palavra (bits) = 32.",
      "source_field": "largura_palavra" }, ... ] }
```

**Leitura:** alguém escreveu o parser da T1.2 localmente, rodou (gerando o
`spec.json` e o `.pyc`), e o arquivo se perdeu — nunca entrou no git.

Agrava o problema: **`outputs/` está no `.gitignore`**. Então o único vestígio
do trabalho é um `.pyc` que também é ignorado. Numa máquina limpa, nada disso
existe.

> **Ação sugerida antes de qualquer coisa:** verificar se `parser.py` sobrou em
> algum backup, editor aberto ou lixeira. O `spec.json` em `outputs/` mostra
> exatamente o formato de saída que ele produzia, então reescrevê-lo é viável —
> mas é retrabalho evitável se a cópia aparecer.

---

## 4. Checkboxes de `tasks.md` que estão desatualizados

A trilha B verificou o ambiente por execução real e isso mudou o estado de três
tarefas da trilha A, sem que os checkboxes tenham sido atualizados:

| Tarefa | Diz | Realidade verificada |
|---|---|---|
| T0.2 — instalar GHDL/cocotb/GTKWave | `[ ]` | **feito.** GHDL 4.1.0, cocotb 2.1.0 em `~/venv-cocotb`, GTKWave — todos presentes na WSL e usados de verdade pela trilha B (ADR-006) |
| T0.3 — Yosys + `ghdl-yosys-plugin` | `[ ]` | **parcial.** Yosys 0.33 instalado e funcionando; o **plugin continua ausente**, contornado por `ghdl synth --out=verilog` (ADR-005) |
| T1.3 — validação no formulário | `[ ]` | **substancialmente feito.** `validate_cross_fields` existe e bloqueia o Submeter |

Não alterei os checkboxes: são da trilha A e a decisão de fechá-los é de quem
retomar. Fica o registro.

---

## 5. O que falta, em ordem

### Fase 0 — Setup

- [ ] **T0.4** — `OPENROUTER_API_KEY` via variável de ambiente e
      `SPECHDL_LLM_MODEL`; testar uma chamada mínima ao SDK.
      **Bloqueia as fases 2, 3 e 6**, que dependem de LLM.
      `.env.example` já existe; `.env` está no `.gitignore`.
- [ ] **T0.5** — exemplo fixo em `legado/` com uma rubrica preenchida, para
      servir de fixture nas fases seguintes. **Bloqueia todos os testes
      pytest da trilha A** (T1.4, T2.4, T4.4, T5.3, T6.3).
- [ ] T0.3 — `ghdl-yosys-plugin`, se for exigido de verdade. A trilha B mostrou
      que dá para medir área sem ele.

### Fase 1 — Ingestão

- [ ] **T1.2** — parser `rubrica.md` → `spec.json` em EARS. **Ver seção 3**:
      já foi escrito uma vez e se perdeu.
- [ ] T1.3 — fechar a validação (o grosso está feito).
- [ ] T1.4 — pytest da fase 1, incluindo caso de rubrica inválida.

### Fases 2 a 6 — nada começou

| Fase | Tarefas | Estado |
|---|---|---|
| 2 — Decomposição arquitetural | T2.1 a T2.4 | pacote `architecture/` vazio |
| 3 — Geração VHDL + testbench | T3.1 a T3.4 | pacote `codegen/` vazio |
| 4 — Verificação | T4.1 a T4.4 | pacote `verification/` vazio |
| 5 — Análise PPA | T5.1 a T5.3 | pacote `ppa/` vazio |
| 6 — Relatório | T6.1 a T6.3 | pacote `report/` vazio |

### Fase 7 — CLI

- [ ] T7.1 — `spechdl web` como comando único (hoje é `streamlit run` ou o
      `.bat`). O `pyproject.toml` atual só configura o pytest; não há
      empacotamento nem console script.
- [ ] T7.2 — flag para rodar uma fase isolada reaproveitando artefatos.
- [ ] T7.3 — README de uso.

**Placar: 2 de 27 tarefas concluídas** (T0.1 estrutura de pastas, T1.1
formulário), mais 3 que estão feitas mas não marcadas (seção 4).

---

## 6. O que a trilha B deixou pronto que a trilha A pode reaproveitar

Vale checar antes de reimplementar do zero — a trilha B resolveu, com execução
real, problemas que a trilha A vai encontrar:

| A trilha A vai precisar de | Já existe em |
|---|---|
| rodar GHDL + cocotb de dentro do Python, capturando exit code | `cpus/rv32i_pipeline/test/rv_build.py` |
| harness cocotb com clock, reset, teto de ciclos, detecção de travamento | `cpus/rv32i_pipeline/test/rv_harness.py` |
| síntese real medindo área, com as armadilhas já mapeadas | `cpus/rv32i_pipeline/tools/synth_ppa.py` + ADR-009 |
| formato de imagem de memória para carregar programa | ADR-003 + `instruction_memory.vhd` |
| fallback quando falta ferramenta, sem instalar nada em silêncio | ADR-004, ADR-005, ADR-006 |

Duas armadilhas que custaram depuração e estão documentadas — a fase 4 vai
esbarrar nas duas:

1. **O VPI do GHDL não expõe arrays 2-D** ao cocotb (ADR-002). Se o gerador da
   fase 3 emitir memória como array 2-D de bytes, a fase 4 não conseguirá
   verificar o resultado.
2. **O cocotb não consegue escrever em ROM** no GHDL — a escrita é
   silenciosamente ignorada (ADR-003). Carregar programa em runtime pelo Python
   está descartado; tem que ser por generic na elaboração.

> **Ressalva de escopo.** O princípio 7 da constituição diz que o core do
> pipeline não é hardcoded para um exercício específico. Reaproveitar qualquer
> coisa de `cpus/rv32i_pipeline/` para `legado/src/spechdl/` exige **generalizar
> primeiro e atualizar a spec antes** — copiar código específico de RISC-V para
> dentro do core violaria o princípio.

---

## 7. Onde ler o resto

| Documento | O quê |
|---|---|
| [`specs/constitution.md`](../specs/constitution.md) | princípios; a Emenda 1 declara as duas trilhas |
| [`specs/spec.md`](../specs/spec.md) | FR-01..FR-15 (trilha A), FR-RV-01..25 (trilha B) |
| [`specs/tasks.md`](../specs/tasks.md) | backlog das duas trilhas |
| [`docs/MUDANCAS.md`](MUDANCAS.md) | o que a trilha B mexeu, e o que não mexeu |
| [`cpus/rv32i_pipeline/RELATORIO.md`](../cpus/rv32i_pipeline/RELATORIO.md) | resultado medido da trilha B |
| `docs/mapa-do-projeto.html` | **desatualizado**: só fases 0–7 da trilha A, zero menções a RISC-V |
