# Comparacao de experimentos (2026-09-30)

| experimento | modelo | tipo | ISA | veredito | RV32I | RV32IM | iteracoes | chamadas | tokens (entrada+saida) | tempo | custo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ia_mono | qwen2.5-coder:14b (local) | monociclo | rv32im | REPROVADO | nao compilou | nao compilou | 12 | 17 | 108065+23648 | 17.0 min | 0 (local) |
| ia_mono_qwen14b | qwen2.5-coder:14b (local) | monociclo | rv32im | REPROVADO | nao compilou | nao compilou | 12 | 17 | 111918+25325 | 18.3 min | 0 (local) |

custo: modelos locais, sem custo em dinheiro (0). Veredito e placar: relatorio final do rvverify de cada sessao.
