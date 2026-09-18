Você é responsável por implementar ou corrigir uma CPU RISC-V RV32I/RV32IM em VHDL.

## Objetivo

Faça a CPU passar pelo validador do repositório. O resultado pode ser
REPROVADO: isso é informação válida. Não relaxe testes nem invente instruções.

## Regras

- Implemente somente a ISA RISC-V exigida pelo manifesto.
- Preserve a semântica de RV32I e, quando habilitado, as oito instruções M.
- Use o `cpu.toml` para declarar fontes na ordem de compilação, clock, reset,
  carga da ROM, observabilidade da RAM/registradores e condição de parada.
- Não use uma instrução mágica de halt: todo programa termina com `j halt`.
- Não declare uma métrica que a CPU não expõe; `null` é melhor que um número
  inventado.

## Fluxo obrigatório

1. Comece copiando `entregas/_modelo/` para uma pasta sua.
2. Faça as alterações somente na sua entrega e preencha `cpu.toml`.
3. Rode `python -m rvverify entregas/seu_nome --keep --workdir relatorio`.
4. Corrija a primeira falha do relatório, sem remover o caso que falhou.
5. Antes de afirmar que terminou, rode a suíte completa sem `--casos`.

## Diagnóstico

Leia o requisito afetado, a entrada, o valor esperado, o obtido e o
`sim.log` do caso. Se o GHDL não estiver disponível, a execução não é
aprovada. Se a suíte reprovar, reporte o veredito e a primeira falha; não
substitua a simulação por raciocínio sobre o código.
