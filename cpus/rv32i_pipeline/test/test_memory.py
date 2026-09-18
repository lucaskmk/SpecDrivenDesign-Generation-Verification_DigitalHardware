#!/usr/bin/env python3
"""Preservação de comportamento das memórias após a refatoração 2D -> 1D.

REQ: FR-RV-07 (comportamento preservado e comprovado por teste), FR-RV-06
(memórias observáveis pelo cocotb), FR-RV-09 (imagem `.ram` consumida pela
ROM), FR-RV-10 (constante VHDL segue como padrão).

Contexto: `data_ram.vhd` e `data_rom.vhd` guardavam os dados em array 2-D de
bytes, que o VPI do GHDL não expõe. O ADR-002 trocou por array 1-D de
palavras de 32 bits. Como isso mexe em bloco de terceiro, FR-RV-07 exige
prova de que o comportamento não mudou — inclusive as regras originais de
acesso desalinhado.

Rodar:
  pytest cpus/rv32i_pipeline/test/test_memory.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rv_build import (  # noqa: E402
    ORIGINAL_REVISION,
    RAM_BASE,
    materialize_original_sources,
    result_addr,
    run_builtin_snapshot,
    run_program,
)

HALT = """
halt:
    j halt
"""

SNAPSHOT_CYCLES = 60


class TestBehaviourPreservation:
    """A/B real: RTL original (do git) vs RTL refatorado, mesmo testbench.

    Em vez de comparar contra números anotados à mão, o design ORIGINAL é
    extraído do commit que o vendorizou e executado pelo MESMO harness. Assim
    a comparação isola exatamente a refatoração das memórias (ADR-002).
    """

    def test_refactor_matches_original_rtl(self, tmp_path):
        """FR-RV-07: PC e todos os 32 registradores idênticos ao original."""
        original_src = materialize_original_sources(tmp_path / "original_src")
        assert (original_src / "data_ram.vhd").exists(), (
            f"não foi possível extrair o RTL original do commit {ORIGINAL_REVISION}"
        )
        # confirma que estamos comparando contra a versão 2-D de verdade
        assert "3 downto 0) of std_logic_vector(7 downto 0)" in (
            original_src / "memory_package.vhd"
        ).read_text(), "o fonte extraído não é o original com arrays 2-D"

        before = run_builtin_snapshot(
            tmp_path, "original", cycles=SNAPSHOT_CYCLES,
            src_dir=original_src,
            requirements=["FR-RV-07"],
        )
        after = run_builtin_snapshot(
            tmp_path, "refactored", cycles=SNAPSHOT_CYCLES,
            requirements=["FR-RV-07"],
        )

        assert after["pc"] == before["pc"], (
            f"PC divergiu após a refatoração: original {before['pc']:#010x}, "
            f"refatorado {after['pc']:#010x} (FR-RV-07)"
        )

        diffs = [
            f"x{i}: original {b:#010x}, refatorado {a:#010x}"
            for i, (b, a) in enumerate(zip(before["registers"], after["registers"]))
            if a != b
        ]
        assert not diffs, (
            "registradores divergiram após a refatoração das memórias "
            "(FR-RV-07):\n  " + "\n  ".join(diffs)
        )

    def test_original_program_still_runs(self, tmp_path):
        """FR-RV-10: o caminho da constante VHDL continua funcionando."""
        snap = run_builtin_snapshot(
            tmp_path, "builtin", cycles=SNAPSHOT_CYCLES,
            requirements=["FR-RV-10"],
        )
        # x28 recebe `var = 11`, valor conhecido do compilation/main.c original
        assert snap["registers"][28] == 0x0B, (
            f"x28 esperado 0x0b (var=11 de compilation/main.c), "
            f"obtido {snap['registers'][28]:#010x}"
        )
        assert snap["pc"] != 0, "a CPU não saiu do endereço de reset"

    def test_data_rom_constants_readable(self, tmp_path):
        """A ROM de dados guardava 0x07 e 0x0b; deve continuar lendo isso.

        O programa original usa `increment = 7` (const) e `var = 11`.
        Aqui lemos a ROM de dados diretamente, por load.
        """
        asm = f"""
        # REQ: FR-RV-07 -- data ROM ainda entrega os mesmos valores
            li   x10, 0x00FC8000        # DATA_MEMORY_BASE_ADDRESS (data ROM)
            lw   x1, 0(x10)             # deve ser 7
            lw   x2, 4(x10)             # deve ser 11
            li   x11, {RAM_BASE}
            sw   x1, 0(x11)
            sw   x2, 4(x11)
        {HALT}
        """
        run = run_program(
            tmp_path, "data_rom_read", asm,
            expect_regs={1: 7, 2: 11},
            expect_ram={result_addr(0): 7, result_addr(1): 11},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )
        assert run.metrics["halted"]


class TestWordAccess:
    def test_word_store_load_roundtrip(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-07 -- acesso de 32 bits
            li   x11, {RAM_BASE}
            li   x1, 0x12345678
            sw   x1, 0(x11)
            lw   x2, 0(x11)             # deve reler 0x12345678
            li   x3, 0xDEADBEEF
            sw   x3, 8(x11)
            lw   x4, 8(x11)
            sw   x2, 4(x11)
            sw   x4, 12(x11)
        {HALT}
        """
        run_program(
            tmp_path, "word_rt", asm,
            expect_regs={2: 0x12345678, 4: 0xDEADBEEF},
            expect_ram={
                result_addr(0): 0x12345678,
                result_addr(1): 0x12345678,
                result_addr(2): 0xDEADBEEF,
                result_addr(3): 0xDEADBEEF,
            },
            max_cycles=500,
            requirements=["FR-RV-07"],
        )


class TestByteAccess:
    def test_byte_lanes_are_little_endian(self, tmp_path):
        """Os quatro byte lanes devem manter a ordem little-endian original."""
        asm = f"""
        # REQ: FR-RV-07 -- little-endian preservado no array 1-D
            li   x11, {RAM_BASE}
            li   x1, 0x11
            li   x2, 0x22
            li   x3, 0x33
            li   x4, 0x44
            sb   x1, 0(x11)
            sb   x2, 1(x11)
            sb   x3, 2(x11)
            sb   x4, 3(x11)
            lw   x5, 0(x11)             # deve ser 0x44332211
            sw   x5, 16(x11)
        {HALT}
        """
        run_program(
            tmp_path, "byte_lanes", asm,
            expect_regs={5: 0x44332211},
            expect_ram={result_addr(0): 0x44332211, result_addr(4): 0x44332211},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )

    def test_lb_sign_extends_and_lbu_zero_extends(self, tmp_path):
        """`extend_32` aplica sinal em LB; LBU deve continuar zero-extend."""
        asm = f"""
        # REQ: FR-RV-07 -- LB/LBU inalterados
            li   x11, {RAM_BASE}
            li   x1, 0x80                # byte 0x80 = -128 com sinal
            sb   x1, 0(x11)
            lb   x2, 0(x11)              # -> 0xFFFFFF80
            lbu  x3, 0(x11)              # -> 0x00000080
            sw   x2, 16(x11)
            sw   x3, 20(x11)
        {HALT}
        """
        run_program(
            tmp_path, "lb_lbu", asm,
            expect_regs={2: 0xFFFFFF80, 3: 0x00000080},
            expect_ram={result_addr(4): 0xFFFFFF80, result_addr(5): 0x00000080},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )

    def test_byte_write_preserves_other_lanes(self, tmp_path):
        """Escrita de byte é read-modify-write no array 1-D: não pode sujar vizinhos."""
        asm = f"""
        # REQ: FR-RV-07 -- escrita de byte nao afeta os outros bytes da palavra
            li   x11, {RAM_BASE}
            li   x1, 0xAABBCCDD
            sw   x1, 0(x11)
            li   x2, 0x99
            sb   x2, 2(x11)              # troca somente o byte 2
            lw   x3, 0(x11)              # -> 0xAA99CCDD
            sw   x3, 16(x11)
        {HALT}
        """
        run_program(
            tmp_path, "byte_preserve", asm,
            expect_regs={3: 0xAA99CCDD},
            expect_ram={result_addr(4): 0xAA99CCDD},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )


class TestHalfwordAccess:
    def test_halfword_lanes(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-07 -- halfword lanes (offset 0 e 2)
            li   x11, {RAM_BASE}
            li   x1, 0x1234
            li   x2, 0x5678
            sh   x1, 0(x11)
            sh   x2, 2(x11)
            lw   x3, 0(x11)              # -> 0x56781234
            lhu  x4, 0(x11)              # -> 0x00001234
            lhu  x5, 2(x11)              # -> 0x00005678
            sw   x3, 16(x11)
            sw   x4, 20(x11)
            sw   x5, 24(x11)
        {HALT}
        """
        run_program(
            tmp_path, "half_lanes", asm,
            expect_regs={3: 0x56781234, 4: 0x00001234, 5: 0x00005678},
            expect_ram={
                result_addr(4): 0x56781234,
                result_addr(5): 0x00001234,
                result_addr(6): 0x00005678,
            },
            max_cycles=500,
            requirements=["FR-RV-07"],
        )

    def test_lh_sign_extends(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-07 -- LH mantem extensao de sinal
            li   x11, {RAM_BASE}
            li   x1, 0x8000
            sh   x1, 0(x11)
            lh   x2, 0(x11)              # -> 0xFFFF8000
            lhu  x3, 0(x11)              # -> 0x00008000
            sw   x2, 16(x11)
            sw   x3, 20(x11)
        {HALT}
        """
        run_program(
            tmp_path, "lh_sign", asm,
            expect_regs={2: 0xFFFF8000, 3: 0x00008000},
            expect_ram={result_addr(4): 0xFFFF8000, result_addr(5): 0x00008000},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )

    def test_halfword_write_preserves_other_half(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-07 -- escrita de halfword nao afeta a outra metade
            li   x11, {RAM_BASE}
            li   x1, 0xAAAABBBB
            sw   x1, 0(x11)
            li   x2, 0x1234
            sh   x2, 0(x11)              # troca somente os 16 bits baixos
            lw   x3, 0(x11)              # -> 0xAAAA1234
            sw   x3, 16(x11)
        {HALT}
        """
        run_program(
            tmp_path, "half_preserve", asm,
            expect_regs={3: 0xAAAA1234},
            expect_ram={result_addr(4): 0xAAAA1234},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )


class TestUnalignedAndOutOfRange:
    """Regras originais: leitura desalinhada devolve 0xFFFFFFFF, escrita é descartada."""

    def test_unaligned_word_read_returns_all_ones(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-07 -- leitura de palavra desalinhada devolve 0xFFFFFFFF
            li   x11, {RAM_BASE}
            li   x1, 0x12345678
            sw   x1, 0(x11)
            lw   x2, 1(x11)              # desalinhado -> 0xFFFFFFFF
            lw   x3, 2(x11)              # desalinhado -> 0xFFFFFFFF
            sw   x2, 16(x11)
            sw   x3, 20(x11)
        {HALT}
        """
        run_program(
            tmp_path, "unaligned_read", asm,
            expect_regs={2: 0xFFFFFFFF, 3: 0xFFFFFFFF},
            expect_ram={result_addr(4): 0xFFFFFFFF, result_addr(5): 0xFFFFFFFF},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )

    def test_unaligned_halfword_read_returns_all_ones(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-07 -- leitura de halfword desalinhada devolve 0xFFFFFFFF
            li   x11, {RAM_BASE}
            li   x1, 0x12345678
            sw   x1, 0(x11)
            lhu  x2, 1(x11)              # desalinhado
            sw   x2, 16(x11)
        {HALT}
        """
        run_program(
            tmp_path, "unaligned_half_read", asm,
            expect_regs={2: 0xFFFFFFFF},
            expect_ram={result_addr(4): 0xFFFFFFFF},
            max_cycles=500,
            requirements=["FR-RV-07"],
        )

    def test_unaligned_word_write_is_discarded(self, tmp_path):
        asm = f"""
        # REQ: FR-RV-07 -- escrita de palavra desalinhada e descartada
            li   x11, {RAM_BASE}
            li   x1, 0xAAAAAAAA
            sw   x1, 0(x11)              # baseline conhecido
            li   x2, 0x55555555
            sw   x2, 1(x11)              # desalinhado: deve ser IGNORADO
            lw   x3, 0(x11)              # continua 0xAAAAAAAA
            sw   x3, 16(x11)
        {HALT}
        """
        run_program(
            tmp_path, "unaligned_write", asm,
            expect_regs={3: 0xAAAAAAAA},
            expect_ram={
                result_addr(0): 0xAAAAAAAA,
                result_addr(4): 0xAAAAAAAA,
            },
            max_cycles=500,
            requirements=["FR-RV-07"],
        )


class TestRamImageInterface:
    def test_rom_consumes_generated_image(self, tmp_path):
        """FR-RV-09: a ROM realmente executa a imagem `.ram` gerada."""
        asm = f"""
        # REQ: FR-RV-09 -- imagem .ram carregada pela ROM
            li   x1, 0x0BADC0DE
            li   x11, {RAM_BASE}
            sw   x1, 0(x11)
        {HALT}
        """
        run = run_program(
            tmp_path, "image_load", asm,
            expect_regs={1: 0x0BADC0DE},
            expect_ram={result_addr(0): 0x0BADC0DE},
            max_cycles=300,
            requirements=["FR-RV-09"],
        )
        assert run.image_path.exists()
        text = run.image_path.read_text()
        assert "# programa: image_load" in text
        # a imagem tem que ser hex de 8 dígitos, uma palavra por linha
        payload = [ln for ln in text.splitlines() if not ln.startswith("#")]
        assert all(len(ln) == 8 for ln in payload if ln), payload

    def test_waveform_is_produced(self, tmp_path):
        """FR-RV-21: a simulação precisa produzir waveform."""
        run = run_program(
            tmp_path, "wave_check", f"    nop\n{HALT}",
            max_cycles=200, waves=True,
            requirements=["FR-RV-21"],
        )
        assert run.waveform is not None and run.waveform.exists(), (
            "nenhum waveform .ghw foi gerado"
        )
        assert run.waveform.stat().st_size > 0
