# Rubrica de especificação — SpecHDL

> A fonte de verdade do schema é
> [`src/spechdl/ingestion/schema.py`](../src/spechdl/ingestion/schema.py) —
> este arquivo é só uma visão geral estrutural, não é pra editar à mão nem
> pra ficar sincronizado campo a campo. O formulário interativo real é
> `streamlit run src/spechdl/ingestion/web_form.py` (ou duplo clique em
> `abrir_formulario.bat`).

## Seções (137 campos ao todo)

1. **Modelo geral da máquina** — largura de palavra/endereço, Harvard vs.
   von Neumann, load/store puro, banco de registradores.
2. **ISA e formato de instrução** — largura/formato de instrução, opcode,
   modos de endereçamento, flags, multiplicação/divisão/shift em hardware,
   ponto flutuante, SIMD.
3. **Microarquitetura (datapath + controle)** — estágios de pipeline, CPI,
   forwarding, predição de desvio, superescalar, execução fora de ordem,
   SMT, número de cores.
4. **Hierarquia de memória** — níveis de cache (0 a 3, com campos
   dinâmicos por nível: L1 unificada ou L1I/L1D separadas, L2, L3),
   política de substituição, coerência entre cores, MMU/TLB, RAM.
5. **E/S, barramento e interrupções** — mapeamento de E/S, interrupções
   (vetorizadas, com prioridade, aninhadas), DMA, periféricos (timer,
   UART, GPIO, watchdog).
6. **Proteção e exceções** — modos de privilégio, proteção de memória,
   exceções precisas.
7. **Implementação física (PPA)** — FPGA vs. ASIC, orçamento de área e
   potência, domínios de clock, reset, debug.
8. **Software / ABI** — assembler, compilador C, SO/RTOS, convenção de
   chamada, pilha.

## Skip logic

Pergunta booleana revela os campos filhos só quando marcada — ex.: "Tem
interrupções?" revela número de linhas/vetorizadas/prioridade/aninhadas;
"Ponto flutuante?" revela largura FP e IEEE-754. Implementado em
`render_field()` (`web_form.py`), lendo o campo `children` do schema.

## Validação cruzada (FR-03)

`validate_cross_fields()` em `schema.py` bloqueia o botão de submissão
enquanto qualquer uma dessas checagens falhar:

- Bits do campo de registrador (derivado: `ceil(log2(nº registradores))`) ×
  operandos + opcode + imediato ≤ largura da instrução.
- `2^(largura do endereço) ≥ RAM + ROM` (espaço de E/S mapeada em memória
  não é somado — o schema não pede o tamanho dela separadamente).
- Por nível de cache ativo: tamanho é múltiplo de associatividade × bloco
  (senão não dá pra formar um número inteiro de conjuntos), e
  associatividade ≤ número de blocos da cache.

## Nota

Schema inicial (T1.1), baseado no esqueleto que você passou. Ainda não é a
rubrica oficial da disciplina; ajustar quando o material exato do
professor estiver disponível (ver `CLAUDE.md`, regra "se o enunciado real
divergir da spec").
