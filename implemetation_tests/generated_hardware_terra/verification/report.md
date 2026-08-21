# Relatorio de verificacao - ULA MIPS de 32 bits

## Rastreabilidade

| Requisitos | Bloco | Implementacao | Teste |
|---|---|---|---|
| FR-01 a FR-09, NFR-01, NFR-02 | `ula32_mips` | `src/ula32_mips.vhd` | `test/test_ula32_mips.py` |
| NFR-03 | `ula32_mips` | Comentario `-- REQ` | Comentario `# REQ` |

## Resultado da verificacao

**Aprovada:** executada em Docker com a imagem
`rafaelcorsi/pl-descomp-cocotb`, GHDL 2.0.0 e cocotb 2.0.0. Os tres testes
passaram e nenhum falhou (`TESTS=3 PASS=3 FAIL=0`), cobrindo 232 ns de
simulacao. O ambiente Windows local nao possui GHDL/cocotb no `PATH`, mas a
execucao conteinerizada e uma verificacao real do DUT.

Para executar quando o toolchain estiver instalado:

```powershell
make -C test SIM=ghdl
```

O testbench cobre operacoes MIPS, overflow modular de 32 bits, comparacao
assinada de `SLT`, flag `zero` e todos os codigos de controle nao suportados.

## PPA

Nao medido. A sintese foi tentada na imagem de referencia, mas o executavel
`yosys` nao esta instalado nela. Assim, Yosys com `ghdl-yosys-plugin` nao esta
disponivel; este relatorio nao apresenta estimativas como metricas sintetizadas.
