# Relatorio de verificacao da ULA32

Data: 2026-08-21

## Resultado

**PASS**: 3 testes aprovados, 0 falhas, 1.221 vetores verificados.

Comando executado a partir de `Generated Hardware`:

```sh
docker run --rm -v "${PWD}:/work" -w /work/test \
  rafaelcorsi/pl-descomp-cocotb make SIM=ghdl
```

Ambiente real de simulacao:

- GHDL 2.0.0 (mcode, Dunoon edition)
- cocotb 2.0.0
- Python 3.11.9
- Imagem de referencia `rafaelcorsi/pl-descomp-cocotb`

## Cobertura

| Requisito | Bloco/codigo | Verificacao | Resultado |
|---|---|---|---|
| FR-01 | `ula32`, `src/ula32.vhd` | Compilacao GHDL e testes combinacionais | PASS |
| FR-02 | `ula32`, `src/ula32.vhd` | Casos dirigidos e 1.200 vetores aleatorios | PASS |
| FR-03 | Logica de `zero` | Flag conferida em todo vetor | PASS |
| FR-04 | Ramo `others` | Todos os 10 controles invalidos | PASS |
| FR-05 | ADD/SUB de 32 bits | Wraparound e referencia modular | PASS |
| FR-06 | SLT signed | Fronteiras positivas/negativas e referencia signed | PASS |
| NFR-01 | Arquitetura combinacional | Design sem clock nem registradores | PASS |
| NFR-02 | VHDL com `numeric_std` | Analise e elaboracao GHDL | PASS |
| NFR-03 | cocotb + Makefile | Execucao completa via GHDL | PASS |

## Artefatos

- Resultado JUnit: `test/results.xml`
- Forma de onda GHDL: `test/ula32.ghw`
- Resultado estruturado: `verification/block_result.json`

## PPA

Metricas de potencia, desempenho e area nao foram sintetizadas nem estimadas.
Nenhum valor de PPA e declarado como medicao neste relatorio.
