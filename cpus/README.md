# CPUs de referência

| Pasta | Contrato | Situação |
|---|---|---|
| [`rv32i_gabarito/`](rv32i_gabarito/) | atual: entidade `cpu` de `specs/cpu.md`, barramento virtual de 9 portas, sem memória dentro | passa nos 24 casos RV32I do `rvverify` |
| [`rv32i_monociclo/`](rv32i_monociclo/) | antigo: topo `cpu_monocycle(rst, clk)` com ROM e RAM dentro e generic `ROM_INIT_FILE` | legado |
| [`rv32i_pipeline/`](rv32i_pipeline/) | antigo: topo `CPU(rst, clk)` com memórias dentro | legado |

As duas CPUs legadas foram escritas para o validador antigo (`tb_generic`,
programa carregado por generic). O `rvverify` atual só testa o contrato
virtual e o `spec-riscv-test` exige a entidade `cpu` exata, então nenhum dos
dois as aceita sem um porte. Elas continuam aqui como material de estudo, e o
`quartus_testing` ainda as usa nos testes dele.

Os testes delas (`cpus/*/test`) ficam fora do `pytest` padrão; rode à parte,
com cocotb instalado: `python -m pytest cpus`.
