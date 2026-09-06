#!/usr/bin/env python3
"""Baseline RV32I — verificação da CPU ORIGINAL, sem a extensão M.

REQ: FR-RV-11 (baseline verificada antes de qualquer extensão), FR-RV-04
(palavra/instrução de 32 bits, x0..x31, x0 sempre zero, load/store),
FR-RV-05 (CPU ligada à ROM e à RAM), FR-RV-22/FR-RV-23 (casos de teste
contra modelo de referência), FR-RV-24 (métricas).

Estratégia (ver specs/plan.md): esta suíte roda com `RV32M_ENABLE=false` e
o montador em modo RV32I puro (`allow_m=False`), de modo que nenhum programa
daqui pode usar RV32M nem por acidente. Se algo falhar DEPOIS da extensão M,
a comparação com esta baseline diz se a culpa é da mudança.

Rodar:
  pytest examples/RISCV32I/test/test_rv32i_baseline.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_model as ref  # noqa: E402
from rv_build import RAM_BASE, result_addr, run_program  # noqa: E402

HALT = """
halt:
    j halt
"""


def _sig(v: int) -> str:
    """Literal decimal com sinal, aceito pelo `li` do montador."""
    v &= 0xFFFFFFFF
    return str(v - (1 << 32) if v & 0x80000000 else v)


def alu_program(op: str, pairs: list[tuple[int, int]], req: str) -> str:
    """Programa que aplica `op` a cada par e grava o resultado na RAM."""
    lines = [
        f"        # REQ: {req} -- {op} sobre valores de borda",
        f"    li   x11, {RAM_BASE}",
    ]
    for i, (a, b) in enumerate(pairs):
        lines += [
            f"    li   x5, {_sig(a)}",
            f"    li   x6, {_sig(b)}",
            f"    {op:<5} x7, x5, x6",
            f"    sw   x7, {4 * i}(x11)",
        ]
    lines.append(HALT)
    return "\n".join(lines)


# Pares de borda: cobre zero, positivos, negativos, maior e menor valor
# representável (FR-RV-22).
CORE_PAIRS = [
    (0x00000000, 0x00000000),
    (0x00000001, 0x00000001),
    (0x00000005, 0x00000003),
    (0xFFFFFFFF, 0x00000001),      # -1, 1
    (0x7FFFFFFF, 0x00000001),      # INT32_MAX, 1  -> overflow modular
    (0x80000000, 0x00000001),      # INT32_MIN, 1
    (0x80000000, 0xFFFFFFFF),      # INT32_MIN, -1
    (0x7FFFFFFF, 0x7FFFFFFF),
    (0xFFFFFFFF, 0xFFFFFFFF),      # -1, -1
    (0x12345678, 0x0000000F),
    (0xDEADBEEF, 0x00000004),
    (0x55555555, 0xAAAAAAAA),
]


class TestArchitecturalBasics:
    """FR-RV-04: propriedades base do RV32I."""

    def test_x0_is_hardwired_to_zero(self, tmp_path):
        """Escrever em x0 deve ser descartado; ler x0 deve dar 0."""
        asm = f"""
        # REQ: FR-RV-04 -- x0 permanentemente zero
            li   x11, {RAM_BASE}
            addi x0, x0, 123            # deve ser descartado
            lui  x0, 0xFFFFF            # deve ser descartado
            add  x0, x0, x0
            sw   x0, 0(x11)             # RAM deve receber 0
            addi x1, x0, 7              # x0 lido como 0 -> x1 = 7
            sw   x1, 4(x11)
        {HALT}
        """
        run_program(
            tmp_path, "x0_zero", asm,
            expect_regs={0: 0, 1: 7},
            expect_ram={result_addr(0): 0, result_addr(1): 7},
            max_cycles=400, requirements=["FR-RV-04"],
        )

    def test_all_31_writable_registers(self, tmp_path):
        """x1..x31 devem existir e guardar valores distintos."""
        lines = ["        # REQ: FR-RV-04 -- banco de x0 a x31"]
        for i in range(1, 32):
            lines.append(f"    li   x{i}, {i * 0x101}")
        lines.append(HALT)
        run_program(
            tmp_path, "all_regs", "\n".join(lines),
            expect_regs={i: i * 0x101 for i in range(1, 32)},
            max_cycles=600, requirements=["FR-RV-04"],
        )

    def test_32bit_word_wraparound(self, tmp_path):
        """Aritmética é modular em 2^32, sem saturação."""
        asm = f"""
        # REQ: FR-RV-04 -- wraparound modular de 32 bits
            li   x11, {RAM_BASE}
            li   x5, -1                 # 0xFFFFFFFF
            addi x6, x5, 1              # deve dar 0, não 0x100000000
            sw   x6, 0(x11)
            li   x7, 2147483647         # INT32_MAX
            addi x8, x7, 1              # deve dar 0x80000000
            sw   x8, 4(x11)
        {HALT}
        """
        run_program(
            tmp_path, "wrap32", asm,
            expect_regs={6: 0, 8: 0x80000000},
            expect_ram={result_addr(0): 0, result_addr(1): 0x80000000},
            max_cycles=400, requirements=["FR-RV-04"],
        )


class TestRegRegArithmetic:
    """FR-RV-22/FR-RV-23: R-type conferido contra o modelo de referência."""

    @pytest.mark.parametrize("op", ["add", "sub", "and", "or", "xor",
                                    "sll", "srl", "sra", "slt", "sltu"])
    def test_r_type_against_reference_model(self, tmp_path, op):
        asm = alu_program(op, CORE_PAIRS, "FR-RV-22")
        expect_ram = {
            result_addr(i): ref.apply_i(op, a, b)
            for i, (a, b) in enumerate(CORE_PAIRS)
        }
        run_program(
            tmp_path, f"rr_{op}", asm,
            expect_ram=expect_ram,
            max_cycles=2000,
            requirements=["FR-RV-22", "FR-RV-23"],
        )


class TestImmediateArithmetic:
    def test_addi_slti_sltiu_logic_immediates(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-22 -- I-type
            li   x11, {RAM_BASE}
            li   x5, 100
            addi x6, x5, 23             # 123
            sw   x6, 0(x11)
            addi x7, x5, -150           # -50
            sw   x7, 4(x11)
            slti x8, x5, 200            # 1
            sw   x8, 8(x11)
            slti x9, x5, 50             # 0
            sw   x9, 12(x11)
            li   x10, -1
            slti x12, x10, 0            # -1 < 0 com sinal -> 1
            sw   x12, 16(x11)
            sltiu x13, x10, 0           # 0xFFFFFFFF < 0 sem sinal -> 0
            sw   x13, 20(x11)
            xori x14, x5, 0xFF
            sw   x14, 24(x11)
            ori  x15, x5, 0xF
            sw   x15, 28(x11)
            andi x16, x5, 0xF
            sw   x16, 32(x11)
        {HALT}
        """
        run_program(
            tmp_path, "imm_arith", asm,
            expect_ram={
                result_addr(0): 123,
                result_addr(1): (-50) & 0xFFFFFFFF,
                result_addr(2): 1,
                result_addr(3): 0,
                result_addr(4): 1,
                result_addr(5): 0,
                result_addr(6): 100 ^ 0xFF,
                result_addr(7): 100 | 0xF,
                result_addr(8): 100 & 0xF,
            },
            max_cycles=800, requirements=["FR-RV-22"],
        )

    def test_shift_immediates(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-22 -- SLLI/SRLI/SRAI
            li   x11, {RAM_BASE}
            li   x5, -16                # 0xFFFFFFF0
            slli x6, x5, 4
            sw   x6, 0(x11)
            srli x7, x5, 4              # logico -> 0x0FFFFFFF
            sw   x7, 4(x11)
            srai x8, x5, 4              # aritmetico -> 0xFFFFFFFF
            sw   x8, 8(x11)
            li   x9, 1
            slli x10, x9, 31            # 0x80000000
            sw   x10, 12(x11)
        {HALT}
        """
        run_program(
            tmp_path, "shift_imm", asm,
            expect_ram={
                result_addr(0): ref.sll(0xFFFFFFF0, 4),
                result_addr(1): ref.srl(0xFFFFFFF0, 4),
                result_addr(2): ref.sra(0xFFFFFFF0, 4),
                result_addr(3): 0x80000000,
            },
            max_cycles=600, requirements=["FR-RV-22"],
        )

    def test_lui_auipc(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-22 -- U-type
            li   x11, {RAM_BASE}
            lui  x5, 0x12345
            sw   x5, 0(x11)             # 0x12345000
        base:
            auipc x6, 0                 # = endereco de `base`
            sw   x6, 4(x11)
        {HALT}
        """
        run = run_program(
            tmp_path, "u_type", asm,
            expect_ram={result_addr(0): 0x12345000},
            max_cycles=400, requirements=["FR-RV-22"],
        )
        assert run.metrics["halted"]


class TestLoadStore:
    """FR-RV-04: load/store para acesso à RAM."""

    def test_store_then_load_all_widths(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-04 -- load/store de 8, 16 e 32 bits
            li   x11, {RAM_BASE}
            li   x5, 0x7F
            sb   x5, 64(x11)
            lb   x6, 64(x11)
            sw   x6, 0(x11)             # 0x7F
            li   x7, 0x7FFF
            sh   x7, 68(x11)
            lh   x8, 68(x11)
            sw   x8, 4(x11)             # 0x7FFF
            li   x9, 0x7FFFFFFF
            sw   x9, 72(x11)
            lw   x10, 72(x11)
            sw   x10, 8(x11)
        {HALT}
        """
        run_program(
            tmp_path, "ls_widths", asm,
            expect_ram={
                result_addr(0): 0x7F,
                result_addr(1): 0x7FFF,
                result_addr(2): 0x7FFFFFFF,
            },
            max_cycles=800, requirements=["FR-RV-04"],
        )

    def test_negative_offset_addressing(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-04 -- offset negativo em load/store
            li   x11, {RAM_BASE}
            addi x12, x11, 64
            li   x5, 0xABCD
            sw   x5, -64(x12)           # escreve em RAM_BASE + 0
            lw   x6, -64(x12)
            sw   x6, 4(x11)
        {HALT}
        """
        run_program(
            tmp_path, "neg_offset", asm,
            expect_ram={result_addr(0): 0xABCD, result_addr(1): 0xABCD},
            max_cycles=500, requirements=["FR-RV-04"],
        )


class TestBranches:
    """FR-RV-22: todos os 6 branches, tomados e não tomados."""

    def test_all_branches_taken_and_not_taken(self, tmp_path):
        # Cada bloco grava 1 se o branch se comportou como esperado.
        asm = f"""
        # REQ: FR-RV-22 -- BEQ/BNE/BLT/BGE/BLTU/BGEU
            li   x11, {RAM_BASE}
            li   x20, 1

            # BEQ tomado
            li   x5, 7
            li   x6, 7
            beq  x5, x6, beq_ok
            j    fail
        beq_ok:
            sw   x20, 0(x11)

            # BEQ nao tomado
            li   x6, 8
            beq  x5, x6, fail
            sw   x20, 4(x11)

            # BNE tomado
            bne  x5, x6, bne_ok
            j    fail
        bne_ok:
            sw   x20, 8(x11)

            # BLT com sinal: -1 < 1
            li   x5, -1
            li   x6, 1
            blt  x5, x6, blt_ok
            j    fail
        blt_ok:
            sw   x20, 12(x11)

            # BLTU sem sinal: 0xFFFFFFFF > 1, entao NAO deve tomar
            bltu x5, x6, fail
            sw   x20, 16(x11)

            # BGE com sinal: 1 >= -1
            bge  x6, x5, bge_ok
            j    fail
        bge_ok:
            sw   x20, 20(x11)

            # BGEU sem sinal: 0xFFFFFFFF >= 1
            bgeu x5, x6, bgeu_ok
            j    fail
        bgeu_ok:
            sw   x20, 24(x11)

            # BGE com iguais
            bge  x6, x6, bge_eq_ok
            j    fail
        bge_eq_ok:
            sw   x20, 28(x11)

            j    done
        fail:
            li   x21, -1
            sw   x21, 32(x11)
        done:
        {HALT}
        """
        run_program(
            tmp_path, "branches", asm,
            expect_ram={result_addr(i): 1 for i in range(8)} | {result_addr(8): 0},
            max_cycles=1000, requirements=["FR-RV-22"],
        )


class TestJumps:
    def test_jal_and_jalr_link_register(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-22 -- JAL/JALR e endereco de retorno
            li   x11, {RAM_BASE}
            li   x20, 0
            jal  x1, subroutine         # x1 = PC+4
            # retorna aqui
            sw   x20, 0(x11)            # deve ser 42 se a subrotina rodou
            j    done
            li   x20, 999               # nunca executado
        subroutine:
            li   x20, 42
            jalr x0, 0(x1)              # volta
        done:
        {HALT}
        """
        run_program(
            tmp_path, "jumps", asm,
            expect_regs={20: 42},
            expect_ram={result_addr(0): 42},
            max_cycles=600, requirements=["FR-RV-22"],
        )

    def test_nested_calls(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-22 -- chamadas encadeadas com salvamento de retorno
            li   x11, {RAM_BASE}
            li   x2, {RAM_BASE + 256}   # ponteiro de pilha simples
            jal  x1, outer
            sw   x20, 0(x11)
            j    done

        outer:
            sw   x1, 0(x2)              # salva retorno
            jal  x1, inner
            lw   x1, 0(x2)              # restaura
            addi x20, x20, 1            # +1 depois do inner
            jalr x0, 0(x1)

        inner:
            li   x20, 10
            jalr x0, 0(x1)

        done:
        {HALT}
        """
        run_program(
            tmp_path, "nested_calls", asm,
            expect_regs={20: 11},
            expect_ram={result_addr(0): 11},
            max_cycles=800, requirements=["FR-RV-22"],
        )


class TestHazards:
    """FR-RV-22: dependências entre instruções no pipeline original."""

    def test_back_to_back_dependency_chain(self, tmp_path):
        """Forwarding EX<-MEM/WB: cada instrução usa o resultado da anterior."""
        asm = f"""
        # REQ: FR-RV-22 -- cadeia de dependencias consecutivas
            li   x11, {RAM_BASE}
            li   x5, 1
            addi x6, x5, 1              # 2
            addi x7, x6, 1              # 3
            addi x8, x7, 1              # 4
            addi x9, x8, 1              # 5
            add  x10, x9, x9            # 10
            sub  x12, x10, x5           # 9
            sw   x12, 0(x11)
        {HALT}
        """
        run = run_program(
            tmp_path, "dep_chain", asm,
            expect_regs={6: 2, 7: 3, 8: 4, 9: 5, 10: 10, 12: 9},
            expect_ram={result_addr(0): 9},
            max_cycles=500, requirements=["FR-RV-22"],
        )
        assert run.metrics["halted"]

    def test_load_use_hazard_causes_stall(self, tmp_path):
        """A CPU precisa dar stall de 1 ciclo em load-use (hazard_control_unit)."""
        asm = f"""
        # REQ: FR-RV-22 -- hazard load-use
            li   x11, {RAM_BASE}
            li   x5, 0x1234
            sw   x5, 64(x11)
            lw   x6, 64(x11)
            addi x7, x6, 1              # usa x6 IMEDIATAMENTE apos o load
            sw   x7, 0(x11)
        {HALT}
        """
        run = run_program(
            tmp_path, "load_use", asm,
            expect_regs={6: 0x1234, 7: 0x1235},
            expect_ram={result_addr(0): 0x1235},
            max_cycles=500, requirements=["FR-RV-22"],
        )
        # o stall tem que ter realmente acontecido
        assert run.metrics["stalls"] > 0, (
            "nenhum stall observado num programa com hazard load-use; "
            "a contagem de stalls não está funcionando"
        )

    def test_branch_taken_causes_flush(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-22 -- hazard de controle
            li   x11, {RAM_BASE}
            li   x5, 1
            beq  x5, x5, target         # sempre tomado -> flush
            li   x5, 999                # deve ser anulado
            li   x5, 888                # deve ser anulado
        target:
            sw   x5, 0(x11)             # deve gravar 1, nao 999/888
        {HALT}
        """
        run = run_program(
            tmp_path, "branch_flush", asm,
            expect_regs={5: 1},
            expect_ram={result_addr(0): 1},
            max_cycles=500, requirements=["FR-RV-22"],
        )
        assert run.metrics["flushes"] > 0, "nenhum flush observado em branch tomado"


class TestLoops:
    def test_sum_loop(self, tmp_path):
        """Laço simples: soma 1..10 = 55."""
        asm = f"""
        # REQ: FR-RV-22 -- laco com dependencia e branch de controle
            li   x11, {RAM_BASE}
            li   x5, 0                  # acumulador
            li   x6, 1                  # i
            li   x7, 11                 # limite
        loop:
            bge  x6, x7, loop_end
            add  x5, x5, x6
            addi x6, x6, 1
            j    loop
        loop_end:
            sw   x5, 0(x11)
        {HALT}
        """
        run_program(
            tmp_path, "sum_loop", asm,
            expect_regs={5: 55},
            expect_ram={result_addr(0): 55},
            max_cycles=2000, requirements=["FR-RV-22"],
        )

    def test_vector_fill_and_sum(self, tmp_path):
        """Preenche um vetor na RAM e soma, exercitando load/store em laço."""
        n = 8
        expected = sum(i * 3 for i in range(n))
        asm = f"""
        # REQ: FR-RV-22 -- vetor em RAM: escrita e leitura em laco
            li   x11, {RAM_BASE}
            addi x12, x11, 64           # base do vetor
            li   x6, 0                  # i
            li   x7, {n}
        fill:
            bge  x6, x7, fill_done
            add  x14, x0, x0
            add  x14, x14, x6
            add  x14, x14, x6
            add  x14, x14, x6           # x14 = 3*i por somas (baseline RV32I, sem MUL)
            slli x15, x6, 2
            add  x16, x12, x15
            sw   x14, 0(x16)
            addi x6, x6, 1
            j    fill
        fill_done:
            li   x5, 0                  # soma
            li   x6, 0
        sum:
            bge  x6, x7, sum_done
            slli x15, x6, 2
            add  x16, x12, x15
            lw   x17, 0(x16)
            add  x5, x5, x17
            addi x6, x6, 1
            j    sum
        sum_done:
            sw   x5, 0(x11)
        {HALT}
        """
        run_program(
            tmp_path, "vector", asm,
            expect_regs={5: expected},
            expect_ram={result_addr(0): expected},
            max_cycles=5000, requirements=["FR-RV-22"],
        )


class TestResetBehaviour:
    def test_reset_starts_at_reset_handler_address(self, tmp_path):
        """FR-RV-15: reset leva o PC para RESET_HANDLER_ADDRESS (0x0)."""
        asm = f"""
        # REQ: FR-RV-15 -- comportamento de reset
            li   x11, {RAM_BASE}
            li   x5, 0xC0DE
            sw   x5, 0(x11)
        {HALT}
        """
        run = run_program(
            tmp_path, "reset_start", asm,
            expect_ram={result_addr(0): 0xC0DE},
            max_cycles=300, requirements=["FR-RV-15"],
        )
        assert run.metrics["halted"]


class TestScopeGuard:
    def test_baseline_cannot_use_rv32m(self, tmp_path):
        """FR-RV-19: um programa de baseline não pode usar RV32M."""
        from rv_assembler import AssemblyError

        asm = f"""
            li   x5, 6
            li   x6, 7
            mul  x7, x5, x6
        {HALT}
        """
        with pytest.raises(AssemblyError, match="RV32M"):
            run_program(tmp_path, "baseline_no_m", asm,
                        rv32m=False, max_cycles=200,
                        requirements=["FR-RV-19"])
