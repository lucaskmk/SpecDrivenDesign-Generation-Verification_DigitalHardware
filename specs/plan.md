# Plano técnico atual

```text
specs/cpu.md + specs/vhdl.md
          ↓
rvgen: instruções → decomposição → VHDL → testes de componente → correção
          ↓
rvverify: programas RISC-V, GHDL e cocotb
          ↓
veredito integrado
```

## Componentes

- `rvgen/`: orquestra o modelo, sessões, correções e testes opcionais.
- `rvverify/`: monta programas, executa a simulação e compara resultados com
  o modelo de referência independente.
- `cpus/`: pacotes e memórias fornecidos para compilação.
- `entregas/`: CPUs geradas e seus artefatos de sessão.

## Comandos

```bash
python -m rvgen gerar entregas/minha_cpu
python -m rvverify entregas/minha_cpu
```

Para depuração por bloco, acrescente:

```bash
--testes-componentes --gates-componentes --regressoes-componentes
```
