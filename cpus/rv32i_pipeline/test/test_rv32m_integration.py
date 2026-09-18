#!/usr/bin/env python3
"""Extensão RV32M — integração no pipeline: hazards, escopo e latência.

REQ: FR-RV-03 (ISA estritamente RISC-V), FR-RV-04 (x0 sempre zero),
FR-RV-12 (extensão RV32IM), FR-RV-15 (comportamento de reset),
FR-RV-16 (seleção RV32I/RV32IM por generic), FR-RV-17 (hazards e latência das
instruções M), FR-RV-19 (baseline não usa RV32M nem por acidente),
FR-RV-21 (waveform, término, travamento), FR-RV-23 (modelo de referência),
FR-RV-24 (métricas).

O ponto central desta suíte é FR-RV-17. A unidade M do ADR-007 é
COMBINACIONAL: ela tem a mesma latência de 1 ciclo da ALU. A consequência
verificável é que instruções M passam pelos mecanismos de hazard que já
existiam — forwarding MEM→EX e WB→EX, stall de load-use, flush de salto — sem
nenhuma lógica nova, e sem introduzir stall próprio. Cada uma dessas
afirmações tem um teste abaixo que a comprova por execução.

Rodar:
  pytest cpus/rv32i_pipeline/test/test_rv32m_integration.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rvverify import reference as ref  # noqa: E402
from rvverify.asm import AssemblyError, assemble  # noqa: E402
from rv_build import RAM_BASE, result_addr, run_program  # noqa: E402
from rvverify.builder import SimulationFailed  # noqa: E402
from rv_m_cases import HALT, sig  # noqa: E402


# ==========================================================================
# 1. Programa misto RV32I + RV32M
# ==========================================================================

class TestMixedProgram:
    def test_loop_with_load_store_branch_mul_and_div(self, tmp_path):
        """Um fluxo único com laço, load/store, branch, MUL, DIV e REM.

        REQ: FR-RV-12, FR-RV-22. Calcula a soma dos quadrados de 1..10
        gravando cada quadrado na RAM e relendo, depois divide o total.
        O esperado é computado em Python com o modelo de referência, não
        escrito à mão.
        """
        n = 10
        squares = [(i * i) & 0xFFFFFFFF for i in range(1, n + 1)]
        total = 0
        for s in squares:
            total = ref.add(total, s)
        q = ref.div(total, 7)
        r = ref.rem(total, 7)

        asm = f"""
        # REQ: FR-RV-12, FR-RV-22 -- RV32I e RV32M no mesmo fluxo
            li   x18, {RAM_BASE}
            addi x19, x18, 64           # area do vetor
            li   x6, 1                  # i
            li   x7, {n + 1}            # limite
        fill:
            bge  x6, x7, fill_done
            mul  x8, x6, x6             # i*i  (RV32M)
            addi x20, x6, -1
            slli x20, x20, 2
            add  x21, x19, x20
            sw   x8, 0(x21)             # vetor[i-1] = i*i
            addi x6, x6, 1
            j    fill
        fill_done:
            li   x5, 0                  # acumulador
            li   x6, 0
            li   x7, {n}
        sum:
            bge  x6, x7, sum_done
            slli x20, x6, 2
            add  x21, x19, x20
            lw   x22, 0(x21)            # rele da RAM
            add  x5, x5, x22
            addi x6, x6, 1
            j    sum
        sum_done:
            sw   x5, 0(x18)             # soma dos quadrados
            li   x9, 7
            div  x10, x5, x9            # RV32M
            sw   x10, 4(x18)
            rem  x11, x5, x9            # RV32M
            sw   x11, 8(x18)
        {HALT}
        """
        run = run_program(
            tmp_path, "mixed", asm,
            expect_regs={5: total, 10: q, 11: r},
            expect_ram={result_addr(0): total,
                        result_addr(1): q,
                        result_addr(2): r},
            max_cycles=5000, rv32m=True,
            requirements=["FR-RV-12", "FR-RV-22", "FR-RV-24"],
        )
        assert run.metrics["m_dispatches"] == n + 2, (
            f"esperava {n + 2} instrucoes RV32M despachadas "
            f"({n} MUL no laco + DIV + REM), obtive {run.metrics['m_dispatches']}"
        )


# ==========================================================================
# 2. Hazards de dados: o forwarding existente carrega resultados da unidade M
# ==========================================================================

class TestDataHazards:
    def test_consumer_immediately_after_m(self, tmp_path):
        """Forwarding MEM→EX: consumidor no ciclo seguinte, sem NOP no meio.

        REQ: FR-RV-17. Se o resultado da unidade M não entrasse em
        `alu_result_e`, o forwarding não o alcançaria e este teste leria o
        valor velho de x12.
        """
        a, b, c = 6, 7, 100
        prod = ref.mul(a, b)
        asm = f"""
        # REQ: FR-RV-17 -- forwarding MEM->EX de resultado RV32M
            li   x18, {RAM_BASE}
            li   x10, {a}
            li   x11, {b}
            li   x13, {c}
            mul  x12, x10, x11
            add  x14, x12, x13          # consome x12 no ciclo seguinte
            sw   x14, 0(x18)
        {HALT}
        """
        run_program(
            tmp_path, "fwd_mem_ex", asm,
            expect_regs={12: prod, 14: ref.add(prod, c)},
            expect_ram={result_addr(0): ref.add(prod, c)},
            max_cycles=500, rv32m=True, requirements=["FR-RV-17"],
        )

    def test_consumer_one_instruction_later(self, tmp_path):
        """Forwarding WB→EX: uma instrução independente no meio."""
        a, b, c = 0x1234, 0x5678, 9
        prod = ref.mul(a, b)
        asm = f"""
        # REQ: FR-RV-17 -- forwarding WB->EX de resultado RV32M
            li   x18, {RAM_BASE}
            li   x10, {a}
            li   x11, {b}
            li   x13, {c}
            mul  x12, x10, x11
            addi x15, x0, 42            # independente, no meio
            add  x14, x12, x13
            sw   x14, 0(x18)
        {HALT}
        """
        run_program(
            tmp_path, "fwd_wb_ex", asm,
            expect_regs={12: prod, 14: ref.add(prod, c), 15: 42},
            expect_ram={result_addr(0): ref.add(prod, c)},
            max_cycles=500, rv32m=True, requirements=["FR-RV-17"],
        )

    def test_chained_dependent_m_instructions(self, tmp_path):
        """M dependente de M, encadeadas sem folga.

        REQ: FR-RV-17. x5 = 3; depois quatro `mul x5, x5, x5` seguidos:
        3 -> 9 -> 81 -> 6561 -> 43046721.
        """
        v = 3
        expected = [v]
        for _ in range(4):
            expected.append(ref.mul(expected[-1], expected[-1]))

        asm = f"""
        # REQ: FR-RV-17 -- cadeia de dependencias entre instrucoes RV32M
            li   x18, {RAM_BASE}
            li   x5, {v}
            mul  x5, x5, x5
            mul  x5, x5, x5
            mul  x5, x5, x5
            mul  x5, x5, x5
            sw   x5, 0(x18)
        {HALT}
        """
        run_program(
            tmp_path, "m_chain", asm,
            expect_regs={5: expected[-1]},
            expect_ram={result_addr(0): expected[-1]},
            max_cycles=500, rv32m=True, requirements=["FR-RV-17"],
        )

    def test_m_result_used_as_memory_address(self, tmp_path):
        """O resultado de uma instrução M vira endereço de store e de load."""
        # 3 * 4 = 12 -> offset de 12 bytes = slot 3
        asm = f"""
        # REQ: FR-RV-17 -- resultado RV32M usado como endereco
            li   x18, {RAM_BASE}
            li   x10, 3
            li   x11, 4
            mul  x12, x10, x11          # 12
            add  x13, x18, x12          # RAM_BASE + 12
            li   x14, {sig(0xCAFE)}
            sw   x14, 0(x13)            # escreve no slot 3
            lw   x15, 0(x13)            # rele do mesmo endereco
            sw   x15, 0(x18)            # e publica no slot 0
        {HALT}
        """
        run_program(
            tmp_path, "m_as_address", asm,
            expect_regs={12: 12, 15: 0xCAFE},
            expect_ram={result_addr(0): 0xCAFE, result_addr(3): 0xCAFE},
            max_cycles=500, rv32m=True, requirements=["FR-RV-17"],
        )

    def test_load_use_stall_with_m_consumer(self, tmp_path):
        """Stall de load-use quando o consumidor é uma instrução M.

        REQ: FR-RV-17. `lw` seguido imediatamente de `mul` que usa o valor
        carregado. O stall é do mecanismo ORIGINAL da CPU; o teste prova que
        ele continua valendo com um consumidor RV32M, e as métricas registram
        que ele de fato aconteceu.
        """
        val = 9
        asm = f"""
        # REQ: FR-RV-17 -- load-use com consumidor RV32M
            li   x18, {RAM_BASE}
            li   x10, {val}
            sw   x10, 32(x18)
            li   x11, 7
            lw   x12, 32(x18)
            mul  x13, x12, x11          # consome x12 vindo da memoria
            sw   x13, 0(x18)
        {HALT}
        """
        run = run_program(
            tmp_path, "load_use_m", asm,
            expect_regs={13: ref.mul(val, 7)},
            expect_ram={result_addr(0): ref.mul(val, 7)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-17", "FR-RV-24"],
        )
        assert run.metrics["stalls"] > 0, (
            "esperava pelo menos um stall de load-use com consumidor RV32M; "
            f"metricas: {run.metrics}"
        )


# ==========================================================================
# 3. Hazard de controle
# ==========================================================================

class TestControlHazards:
    def test_branch_that_depends_on_an_m_result(self, tmp_path):
        """Branch cujo operando vem de uma instrução M imediatamente anterior.

        REQ: FR-RV-17. O branch é resolvido em EX e precisa do resultado da
        unidade M por forwarding; se o forwarding falhasse, o desvio iria para
        o lado errado e o slot 0 ficaria com o valor errado.
        """
        asm = f"""
        # REQ: FR-RV-17 -- hazard de controle dependendo de resultado RV32M
            li   x18, {RAM_BASE}
            li   x10, 6
            li   x11, 7
            li   x13, 42
            mul  x12, x10, x11          # 42
            beq  x12, x13, taken        # depende do resultado da MUL
            li   x14, 111               # nao deve executar
            sw   x14, 0(x18)
            j    fim
        taken:
            li   x14, 222
            sw   x14, 0(x18)
        fim:
        {HALT}
        """
        run = run_program(
            tmp_path, "branch_on_m", asm,
            expect_regs={14: 222}, expect_ram={result_addr(0): 222},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-17", "FR-RV-24"],
        )
        assert run.metrics["flushes"] > 0, (
            f"branch tomado deveria gerar flush; metricas: {run.metrics}"
        )

    def test_m_instruction_right_after_a_taken_branch_is_not_corrupted(self, tmp_path):
        """Uma instrução M logo depois de um salto tomado.

        REQ: FR-RV-17. O flush deixa `alu_op_type_e` com o valor anterior, mas
        zera `write_rd_e` — a bolha não pode escrever registrador nem ser
        contada como instrução M.
        """
        asm = f"""
        # REQ: FR-RV-17 -- bolha de flush nao vira instrucao RV32M
            li   x18, {RAM_BASE}
            li   x10, 5
            li   x11, 5
            li   x20, 777
            j    destino
            mul  x20, x10, x11          # pulada: x20 tem de continuar 777
        destino:
            mul  x21, x10, x11          # 25
            sw   x20, 0(x18)
            sw   x21, 4(x18)
        {HALT}
        """
        run = run_program(
            tmp_path, "flush_then_m", asm,
            expect_regs={20: 777, 21: ref.mul(5, 5)},
            expect_ram={result_addr(0): 777, result_addr(1): ref.mul(5, 5)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-17", "FR-RV-24"],
        )
        assert run.metrics["m_dispatches"] == 1, (
            "a MUL pulada pelo salto nao pode contar como instrucao RV32M "
            f"despachada; metricas: {run.metrics}"
        )


# ==========================================================================
# 4. Latência: a evidência experimental do ADR-007
# ==========================================================================

class TestLatency:
    @staticmethod
    def _template(mnemonic: str, count: int) -> str:
        body = "\n".join(
            f"    {mnemonic} x12, x10, x11" for _ in range(count)
        )
        return f"""
        # REQ: FR-RV-17 -- comparacao de latencia
            li   x18, {RAM_BASE}
            li   x10, 3
            li   x11, 5
{body}
            sw   x12, 0(x18)
        {HALT}
        """

    @pytest.mark.parametrize("mnemonic", ["mul", "mulh", "div", "rem"])
    def test_m_costs_the_same_cycles_as_an_add(self, tmp_path, mnemonic):
        """Uma instrução M custa exatamente os mesmos ciclos que um ADD.

        REQ: FR-RV-17, FR-RV-24. Esta é a comprovação EXPERIMENTAL do ADR-007:
        a unidade M é combinacional, logo tem latência de 1 ciclo, logo não
        introduz stall nenhum. Dois programas com a MESMA estrutura, um com
        `add` e outro com a instrução M, têm de gastar o mesmo número de
        ciclos.

        Se algum dia a unidade virar multiciclo iterativa (trabalho futuro do
        ADR-007), este teste falha — e é isso que se quer: a falha avisa que a
        premissa de latência mudou e que o relatório precisa ser refeito.
        """
        n = 20
        base = run_program(
            tmp_path, f"lat_add_{mnemonic}", self._template("add", n),
            max_cycles=2000, rv32m=True, requirements=["FR-RV-17"],
        )
        m_run = run_program(
            tmp_path, f"lat_{mnemonic}", self._template(mnemonic, n),
            max_cycles=2000, rv32m=True, requirements=["FR-RV-17"],
        )
        assert m_run.metrics["m_dispatches"] == n, (
            f"esperava {n} despachos RV32M, obtive {m_run.metrics['m_dispatches']}"
        )
        assert m_run.metrics["stalls"] == 0, (
            "a unidade M do ADR-007 e combinacional e nao pode gerar stall; "
            f"metricas: {m_run.metrics}"
        )
        assert m_run.cycles == base.cycles, (
            f"{n}x `{mnemonic}` gastou {m_run.cycles} ciclos contra "
            f"{base.cycles} de {n}x `add`. Se a diferenca for real, a unidade "
            f"M deixou de ser de 1 ciclo e o ADR-007 precisa ser revisto -- "
            f"NAO ajuste este teste sem atualizar o ADR."
        )


# ==========================================================================
# 5. Reset
# ==========================================================================

class TestReset:
    def test_registers_are_zero_after_reset(self, tmp_path):
        """FR-RV-15: o reset zera o banco de registradores.

        O programa grava registradores que nunca escreveu. Se o reset não os
        tivesse zerado, os slots viriam com lixo.
        """
        asm = f"""
        # REQ: FR-RV-15, FR-RV-04 -- estado inicial apos o reset
            li   x18, {RAM_BASE}
            sw   x1,  0(x18)
            sw   x5,  4(x18)
            sw   x20, 8(x18)
            sw   x31, 12(x18)
            sw   x0,  16(x18)
        {HALT}
        """
        run_program(
            tmp_path, "reset_state", asm,
            expect_regs={i: 0 for i in (0, 1, 5, 20, 31)},
            expect_ram={result_addr(i): 0 for i in range(5)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-15", "FR-RV-04"],
        )

    def test_execution_starts_at_the_reset_handler_address(self, tmp_path):
        """FR-RV-15: a primeira instrução executada é a do endereço 0x0."""
        asm = f"""
        # REQ: FR-RV-15 -- RESET_HANDLER_ADDRESS = 0x00000000
            li   x5, 1                  # primeira instrucao, em 0x0
            li   x18, {RAM_BASE}
            sw   x5, 0(x18)
        {HALT}
        """
        run_program(
            tmp_path, "reset_pc", asm,
            expect_regs={5: 1}, expect_ram={result_addr(0): 1},
            max_cycles=500, rv32m=True, requirements=["FR-RV-15"],
        )

    def test_reset_behaviour_is_identical_in_both_configurations(self, tmp_path):
        """FR-RV-15/FR-RV-16: ligar RV32M não muda o comportamento de reset."""
        asm = f"""
        # REQ: FR-RV-15, FR-RV-16
            li   x18, {RAM_BASE}
            sw   x9, 0(x18)
            addi x9, x9, 5
            sw   x9, 4(x18)
        {HALT}
        """
        for rv32m in (False, True):
            run_program(
                tmp_path, f"reset_cfg_{rv32m}", asm,
                expect_regs={9: 5},
                expect_ram={result_addr(0): 0, result_addr(1): 5},
                max_cycles=500, rv32m=rv32m,
                requirements=["FR-RV-15", "FR-RV-16"],
            )


# ==========================================================================
# 6. Guardas de escopo: RV32I puro e ISA estritamente RISC-V
# ==========================================================================

class TestScopeGuards:
    M_MNEMONICS = ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"]

    @pytest.mark.parametrize("mnemonic", M_MNEMONICS)
    def test_baseline_cannot_assemble_rv32m(self, mnemonic):
        """FR-RV-19: um programa de baseline não usa RV32M nem por acidente.

        `allow_m=False` é o que a suíte RV32I usa, e ele rejeita a montagem —
        então não há como um teste de baseline passar usando a extensão.
        """
        with pytest.raises(AssemblyError, match="RV32M"):
            assemble(f"{mnemonic} x5, x6, x7", allow_m=False)

    @pytest.mark.parametrize("mnemonic", M_MNEMONICS)
    def test_rv32m_assembles_when_allowed(self, mnemonic):
        """A mesma instrução monta normalmente com `allow_m=True`."""
        words = assemble(f"{mnemonic} x5, x6, x7", allow_m=True)
        assert len(words) == 1
        assert words[0] & 0x7F == 0b0110011, "opcode tem de ser REG_REG (R-type)"
        assert (words[0] >> 25) & 0x7F == 0b0000001, \
            "funct7 da extensao M tem de ser 0000001 (FR-RV-13)"

    def test_running_an_rv32m_program_with_the_generic_off_is_refused(self, tmp_path):
        """FR-RV-16/FR-RV-19: `rv32m=False` também fecha o montador.

        `run_program` faz `allow_m` acompanhar `rv32m` por padrão, de modo que
        a configuração de baseline é coerente de ponta a ponta: nem o hardware
        decodifica RV32M, nem o montador o produz.
        """
        asm = f"""
            li   x18, {RAM_BASE}
            li   x10, 3
            li   x11, 4
            mul  x12, x10, x11
            sw   x12, 0(x18)
        {HALT}
        """
        with pytest.raises(AssemblyError, match="RV32M"):
            run_program(tmp_path, "scope_guard", asm, rv32m=False,
                        max_cycles=200, requirements=["FR-RV-16", "FR-RV-19"])

    def test_isa_is_strictly_risc_v(self):
        """FR-RV-03: nada fora do RV32I/RV32M é aceito."""
        for bogus in ("frobnicate x1, x2, x3", "madd x1, x2, x3, x4",
                      "lw.mips x1, 0(x2)", "halt"):
            with pytest.raises(AssemblyError):
                assemble(bogus, allow_m=True)

    def test_unimplemented_risc_v_instructions_are_refused_by_default(self):
        """FR-RV-03: FENCE, ECALL e EBREAK existem no RISC-V mas NÃO nesta CPU.

        O decoder as marca como inválidas (ADR-000), então o montador as
        rejeita por padrão em vez de deixar o programa cair em comportamento
        indefinido.
        """
        for mnemonic in ("ecall", "ebreak", "fence"):
            with pytest.raises(AssemblyError, match="CPU alvo"):
                assemble(mnemonic, allow_m=True)


# ==========================================================================
# 7. Waveform e detecção de travamento
# ==========================================================================

class TestObservability:
    def test_waveform_is_produced(self, tmp_path):
        """FR-RV-21: a simulação produz waveform inspecionável no GTKWave."""
        asm = f"""
        # REQ: FR-RV-21 -- waveform
            li   x18, {RAM_BASE}
            li   x10, 12345
            li   x11, 7
            mul  x12, x10, x11
            div  x13, x10, x11
            rem  x14, x10, x11
            sw   x12, 0(x18)
            sw   x13, 4(x18)
            sw   x14, 8(x18)
        {HALT}
        """
        run = run_program(
            tmp_path, "waveform", asm,
            expect_ram={result_addr(0): ref.mul(12345, 7),
                        result_addr(1): ref.div(12345, 7),
                        result_addr(2): ref.rem(12345, 7)},
            max_cycles=500, rv32m=True, waves=True,
            requirements=["FR-RV-21"],
        )
        assert run.waveform is not None, "nenhum waveform foi devolvido"
        assert run.waveform.exists(), f"waveform nao existe: {run.waveform}"
        assert run.waveform.stat().st_size > 0, "waveform vazio"

    def test_a_hung_program_is_detected_and_fails(self, tmp_path):
        """FR-RV-21: travamento é detectado e sai com exit code != 0.

        Um laço infinito que NÃO é o auto-laço de parada tem de estourar o teto
        de ciclos. Isso prova que o harness não declara sucesso por omissão --
        se ele apenas rodasse até `max_cycles` e conferisse a RAM, um programa
        travado passaria silenciosamente.

        A cadeia de propagação é: o harness levanta `CpuTimeout`, o testbench
        cocotb o converte em `AssertionError` apontando FR-RV-21, o cocotb
        reprova a simulação, o GHDL termina com exit code != 0 e o runner
        termina com exit code != 0. `rvverify.builder.run_simulation` traduz
        isso em `SimulationFailed`, que é o que chega aqui.

        Por que `SimulationFailed` e não `SystemExit`: o runner do cocotb chama
        `sys.exit()` quando roda SOB PYTEST e não confere nada fora dele. O
        validador normaliza os dois casos num tipo único, para que quem chama
        trate UM. `SimulationFailed` herda de `AssertionError`, então continua
        sendo reprovação de teste, e carrega o exit code na mensagem.
        """
        asm = f"""
        # REQ: FR-RV-21 -- deteccao de travamento
            li   x18, {RAM_BASE}
            li   x5, 0
        preso:
            addi x5, x5, 1
            mul  x6, x5, x5
            beq  x0, x0, preso          # laco infinito, nao e o auto-laco
        halt:
            j    halt
        """
        with pytest.raises(SimulationFailed) as exc:
            run_program(tmp_path, "hang", asm, rv32m=True, max_cycles=300,
                        requirements=["FR-RV-21"])
        assert "exit code" in str(exc.value), (
            f"a reprovacao tem de reportar o exit code; veio: {exc.value}"
        )

    def test_a_wrong_result_also_fails_with_a_nonzero_exit_code(self, tmp_path):
        """FR-RV-21: resultado errado reprova, não passa em silêncio.

        Contraprova do teste acima: aqui o programa TERMINA normalmente, mas o
        valor esperado está deliberadamente errado. O testbench tem de
        reprovar. Sem este caso, um harness que nunca compara nada passaria em
        todos os outros testes.
        """
        asm = f"""
        # REQ: FR-RV-21 -- o testbench realmente compara
            li   x18, {RAM_BASE}
            li   x10, 6
            li   x11, 7
            mul  x12, x10, x11          # 42
            sw   x12, 0(x18)
        {HALT}
        """
        with pytest.raises(SimulationFailed) as exc:
            run_program(tmp_path, "wrong_expect", asm, rv32m=True,
                        expect_ram={result_addr(0): 43},   # errado de proposito
                        max_cycles=300, requirements=["FR-RV-21"])
        assert "exit code" in str(exc.value), (
            f"a reprovacao tem de reportar o exit code; veio: {exc.value}"
        )
