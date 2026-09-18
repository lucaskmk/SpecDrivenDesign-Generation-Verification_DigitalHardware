#!/usr/bin/env python3
"""Biblioteca de benchmarks versionada em `cpus/rv32i_pipeline/programs/`.

REQ: FR-RV-18 (benchmarks .c como especificação legível), FR-RV-19 (programas
.asm, e prova de que os de baseline são RV32I puro), FR-RV-13 (MUL, DIV, REM),
FR-RV-14 (casos especiais da divisão), FR-RV-17 (load/store, laço e
multiplicação no mesmo pipeline), FR-RV-22 (valores de borda), FR-RV-23
(valores esperados vêm do modelo de referência, nunca escritos à mão),
FR-RV-24 (métricas de ciclos para a comparação RV32I x RV32IM).

O que esta suíte prova, em quatro camadas:

1. Cada `.asm` monta, e a imagem `.ram` versionada ao lado é exatamente o que
   o montador produz hoje — imagem obsoleta é falha de teste, não surpresa
   em tempo de simulação.
2. Todo `*_rv32i.asm` monta com `allow_m=False`: é RV32I puro por construção.
3. Todo `*_rv32im.asm` é REJEITADO com `allow_m=False`: prova que ele de fato
   usa a extensão M, e não é só uma cópia com outro nome.
4. Cada programa roda de verdade no GHDL e os resultados publicados na RAM
   batem com o modelo de referência — e as duas versões do mesmo benchmark
   publicam exatamente as mesmas palavras, que é o que dá sentido a comparar
   os ciclos das duas.

Os valores de ENTRADA abaixo espelham os `.c`; os valores ESPERADOS são
sempre calculados por `rvverify.reference` (FR-RV-23).

Rodar:
  pytest cpus/rv32i_pipeline/test/test_programs.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rvverify import reference as ref  # noqa: E402
from rv_build import TOOLS, result_addr, run_program  # noqa: E402

sys.path.insert(0, str(TOOLS))

from build_programs import (  # noqa: E402
    PROGRAMS,
    RV32I_SUFFIX,
    RV32IM_SUFFIX,
    allows_m,
    asm_sources,
    build_one,
    image_path,
)
from rvverify.asm import AssemblyError, assemble, read_ram_image  # noqa: E402

MASK32 = 0xFFFFFFFF


def u32(value: int) -> int:
    """Palavra de 32 bits sem sinal, como o hardware enxerga."""
    return value & MASK32


# --------------------------------------------------------------------------
# Entradas de cada benchmark — espelham os arquivos .c ao lado dos .asm.
# Os RESULTADOS esperados nunca aparecem aqui: saem do modelo de referência.
# --------------------------------------------------------------------------

MUL_PAIRS = [
    (7, 6),                       # positivos pequenos
    (123, 456),                   # ainda cabe em 32 bits
    (-3, 5),                      # sinais misturados
    (-7, -8),                     # ambos negativos
    (65535, 65537),               # maior produto que ainda cabe: 2^32-1
    (2147483647, 2),              # INT32_MAX * 2, estoura
    (-2147483648, 3),             # INT32_MIN * 3, estoura
    (0, 305419896),               # operando zero
]

DIV_CASES = [
    (100, 7),                     # ambos positivos
    (-100, 7),                    # dividendo negativo
    (100, -7),                    # divisor negativo
    (-100, -7),                   # ambos negativos
    (7, 0),                       # divisão por zero (FR-RV-14)
    (-2147483648, -1),            # overflow com sinal (FR-RV-14)
    (2147483647, 2),              # INT32_MAX / 2
    (-2147483648, 3),             # magnitude usa toda a faixa sem sinal
]

DOT_A = [1, 2, 3, -4, 5, -6, 7, 100000]
DOT_B = [10, -20, 30, 40, 50, 60, 70, 100000]
DOT_VEC_A_ADDR = result_addr(32)      # 0x00FC8180
DOT_VEC_B_ADDR = result_addr(40)      # 0x00FC81A0

INT32_MAX = 0x7FFFFFFF
INT32_MIN = 0x80000000
MINUS_ONE = 0xFFFFFFFF


# --------------------------------------------------------------------------
# Resultados esperados — SEMPRE calculados pelo modelo de referência
# --------------------------------------------------------------------------

def expected_mul() -> dict[int, int]:
    """FR-RV-13: 32 bits baixos de a*b, um por slot."""
    return {result_addr(i): ref.mul(u32(a), u32(b))
            for i, (a, b) in enumerate(MUL_PAIRS)}


def expected_div() -> dict[int, int]:
    """FR-RV-13/14: slot 2i = quociente do caso i, slot 2i+1 = resto."""
    out: dict[int, int] = {}
    for i, (a, b) in enumerate(DIV_CASES):
        out[result_addr(2 * i)] = ref.div(u32(a), u32(b))
        out[result_addr(2 * i + 1)] = ref.rem(u32(a), u32(b))
    return out


def expected_dotprod() -> dict[int, int]:
    """FR-RV-17: produto escalar, somas de conferência e os próprios vetores."""
    dot = sum_a = sum_b = 0
    for a, b in zip(DOT_A, DOT_B):
        dot = ref.add(dot, ref.mul(u32(a), u32(b)))
        sum_a = ref.add(sum_a, u32(a))
        sum_b = ref.add(sum_b, u32(b))

    out = {
        result_addr(0): dot,
        result_addr(1): sum_a,
        result_addr(2): sum_b,
        result_addr(3): len(DOT_A),
    }
    # os vetores também são conferidos: um store errado na inicialização
    # apareceria aqui, e não só como produto escalar errado
    for i, a in enumerate(DOT_A):
        out[DOT_VEC_A_ADDR + 4 * i] = u32(a)
    for i, b in enumerate(DOT_B):
        out[DOT_VEC_B_ADDR + 4 * i] = u32(b)
    return out


def expected_signs() -> dict[int, int]:
    """FR-RV-22: extremos da faixa com sinal e overflow modular de 32 bits."""
    values = [
        ref.add(INT32_MAX, 1),          # slot 0
        ref.add(INT32_MIN, MINUS_ONE),  # slot 1
        ref.sub(0, INT32_MIN),          # slot 2
        ref.mul(INT32_MIN, MINUS_ONE),  # slot 3
        ref.mul(INT32_MAX, 2),          # slot 4
        ref.mul(INT32_MIN, INT32_MIN),  # slot 5
        ref.mul(INT32_MAX, INT32_MAX),  # slot 6
        ref.slt(INT32_MIN, INT32_MAX),  # slot 7
        ref.sltu(INT32_MIN, INT32_MAX), # slot 8
        ref.sra(INT32_MIN, 31),         # slot 9
        ref.srl(INT32_MIN, 31),         # slot 10
        ref.mul(MINUS_ONE, MINUS_ONE),  # slot 11
    ]
    return {result_addr(i): v for i, v in enumerate(values)}


# nome do benchmark -> (função de resultados esperados, teto de ciclos,
#                       requisitos cobertos)
BENCHMARKS = {
    "bench_mul": (expected_mul, 20000,
                  ["FR-RV-13", "FR-RV-22", "FR-RV-24"]),
    "bench_div": (expected_div, 40000,
                  ["FR-RV-13", "FR-RV-14", "FR-RV-22", "FR-RV-24"]),
    "bench_dotprod": (expected_dotprod, 20000,
                      ["FR-RV-13", "FR-RV-17", "FR-RV-24"]),
    "bench_signs": (expected_signs, 20000,
                    ["FR-RV-13", "FR-RV-22", "FR-RV-24"]),
}

ISAS = ["rv32i", "rv32im"]

SOURCES = asm_sources()
SOURCE_IDS = [p.name for p in SOURCES]

# ciclos medidos, preenchidos pelas execuções reais e lidos no fim para a
# comparação de eficiência (FR-RV-24)
_measured_cycles: dict[tuple[str, str], int] = {}


def program_path(bench: str, isa: str) -> Path:
    return PROGRAMS / f"{bench}_{isa}.asm"


# --------------------------------------------------------------------------

class TestBibliotecaCompleta:
    """A biblioteca tem os pares esperados e nada solto no diretório."""

    def test_todos_os_benchmarks_tem_as_duas_versoes(self):
        """FR-RV-19/FR-RV-24: comparar ISAs exige o MESMO algoritmo nas duas."""
        faltando = [f"{b}_{isa}.asm"
                    for b in BENCHMARKS for isa in ISAS
                    if not program_path(b, isa).exists()]
        assert not faltando, f"programas ausentes: {faltando}"

    def test_todo_benchmark_tem_o_c_de_especificacao(self):
        """FR-RV-18: o .c é a especificação legível do algoritmo."""
        faltando = [f"{b}.c" for b in BENCHMARKS
                    if not (PROGRAMS / f"{b}.c").exists()]
        assert not faltando, f"especificações .c ausentes: {faltando}"

    def test_o_c_avisa_que_nao_foi_compilado(self):
        """FR-RV-20/ADR-004: não existe compilador RISC-V neste ambiente."""
        for bench in BENCHMARKS:
            texto = (PROGRAMS / f"{bench}.c").read_text(encoding="utf-8")
            assert "NOT COMPILED IN THIS ENVIRONMENT" in texto, bench
            assert "ADR-004" in texto, bench

    def test_nenhum_asm_fora_da_convencao_de_nome(self):
        """O sufixo é o que seleciona o modo do montador (FR-RV-19)."""
        fora = [p.name for p in SOURCES
                if not (p.name.endswith(RV32I_SUFFIX)
                        or p.name.endswith(RV32IM_SUFFIX))]
        assert not fora, f"nomes fora da convenção: {fora}"


class TestImagensVersionadas:
    """A imagem `.ram` no repositório é a que o montador produz agora."""

    @pytest.mark.parametrize("source", SOURCES, ids=SOURCE_IDS)
    def test_imagem_bate_com_o_montador(self, source: Path):
        """FR-RV-08/FR-RV-09: imagem obsoleta falha aqui, não na simulação."""
        montado = build_one(source, write=False)
        imagem = image_path(source)
        assert imagem.exists(), (
            f"{imagem.name} não existe; rode "
            f"`python cpus/rv32i_pipeline/tools/build_programs.py`"
        )
        gravado = read_ram_image(imagem)
        assert gravado == montado.words, (
            f"{imagem.name} está desatualizada em relação a {source.name} "
            f"({len(gravado)} palavras gravadas, {len(montado.words)} montadas)."
            f" Rode `python cpus/rv32i_pipeline/tools/build_programs.py`."
        )

    @pytest.mark.parametrize("source", SOURCES, ids=SOURCE_IDS)
    def test_programa_tem_auto_laco_de_parada(self, source: Path):
        """ADR-003/FR-RV-21: término determinístico."""
        montado = build_one(source, write=False)
        assert montado.halt_pcs, f"{source.name} não tem `halt: j halt`"


class TestIsaDeCadaPrograma:
    """A separação RV32I x RV32IM é verificada pelo montador, não prometida."""

    @pytest.mark.parametrize("source",
                             [p for p in SOURCES if p.name.endswith(RV32I_SUFFIX)],
                             ids=[p.name for p in SOURCES
                                  if p.name.endswith(RV32I_SUFFIX)])
    def test_baseline_monta_como_rv32i_puro(self, source: Path):
        """FR-RV-19: nenhum programa de baseline usa RV32M nem por acidente."""
        assert allows_m(source) is False
        palavras = assemble(source.read_text(encoding="utf-8"), allow_m=False)
        assert palavras, f"{source.name} montou vazio"

    @pytest.mark.parametrize("source",
                             [p for p in SOURCES if p.name.endswith(RV32IM_SUFFIX)],
                             ids=[p.name for p in SOURCES
                                  if p.name.endswith(RV32IM_SUFFIX)])
    def test_versao_m_e_rejeitada_como_rv32i(self, source: Path):
        """FR-RV-12: a versão RV32IM realmente usa a extensão M.

        Se ela montasse com `allow_m=False`, seria apenas uma cópia com outro
        nome, e a comparação de eficiência não estaria comparando ISA nenhuma.
        """
        assert allows_m(source) is True
        with pytest.raises(AssemblyError) as excinfo:
            assemble(source.read_text(encoding="utf-8"), allow_m=False)
        assert "RV32M" in str(excinfo.value)


class TestExecucaoNaCpu:
    """Execução real no GHDL, resultados conferidos contra o modelo."""

    @pytest.mark.parametrize("isa", ISAS)
    @pytest.mark.parametrize("bench", sorted(BENCHMARKS))
    def test_benchmark_publica_os_resultados_esperados(self, tmp_path,
                                                       bench: str, isa: str):
        """FR-RV-23: cada palavra da RAM vem do modelo de referência."""
        esperado, max_cycles, requisitos = BENCHMARKS[bench]
        source = program_path(bench, isa)
        run = run_program(
            tmp_path,
            f"{bench}_{isa}",
            source.read_text(encoding="utf-8"),
            expect_ram=esperado(),
            max_cycles=max_cycles,
            rv32m=(isa == "rv32im"),
            requirements=requisitos + ["FR-RV-19" if isa == "rv32i"
                                       else "FR-RV-12"],
        )
        assert run.cycles > 0
        assert run.instructions > 0
        _measured_cycles[(bench, isa)] = run.cycles


class TestEficiencia:
    """FR-RV-24: a extensão M tem que aparecer na contagem de ciclos."""

    @pytest.mark.parametrize("bench", sorted(BENCHMARKS))
    def test_rv32im_gasta_menos_ciclos_que_rv32i(self, bench: str):
        """Mesmo algoritmo, mesmos resultados: só a ISA muda."""
        base = _measured_cycles.get((bench, "rv32i"))
        m = _measured_cycles.get((bench, "rv32im"))
        if base is None or m is None:
            pytest.skip("execuções na CPU não rodaram nesta seleção de testes")
        assert m < base, (
            f"{bench}: RV32IM gastou {m} ciclos e RV32I gastou {base}; "
            f"a extensão M deveria eliminar a emulação por software"
        )
