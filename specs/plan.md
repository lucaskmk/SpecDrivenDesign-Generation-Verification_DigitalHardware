# Plano técnico atual

```text
specs/cpu.md + specs/vhdl.md
          ↓
rvgen: instruções → decomposição → VHDL → testes de componente → correção
          ↓
spec-riscv-test: programas oficiais do riscv-tests, GHDL e cocotb
          ↓
veredito integrado
```

## Componentes

- `rvgen/`: orquestra o modelo, sessões, correções e testes opcionais.
- `spec-riscv-test/`: juiz do `rvgen`. Compila e roda os programas oficiais
  `riscv-tests` (`rv32ui`, mais `rv32um` para RV32IM) contra a entidade `cpu`
  de `specs/cpu.md`. Só roda em Linux/WSL2.
- `rvverify/`: valida uma entrega descrita por `cpu.toml`: monta programas,
  executa a simulação e compara resultados com um modelo de referência
  independente. Usa o mesmo barramento virtual de `specs/cpu.md`.
- `cpus/`: CPUs de referência. `cpus/rv32i_gabarito` segue o contrato atual;
  `rv32i_monociclo` e `rv32i_pipeline` seguem o contrato antigo (legado).
- `entregas/`: CPUs de alunos e CPUs geradas, com seus artefatos de sessão.

## Comandos

```bash
python -m rvgen gerar minha_cpu                   # grava em experimentos/minha_cpu
python -m rvverify entregas/minha_cpu             # entregas com cpu.toml
spec-riscv-test --cpu experimentos/minha_cpu --riscv-tests riscv-tests --out out
```

Para depuração por bloco, acrescente:

```bash
--testes-componentes --gates-componentes --regressoes-componentes
```
