"""CLI orchestration: compile official sources, run Cocotb, emit LLM-ready JSON."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .contract import sources_for, validate_top
from .elf import ElfError, load


RV32I_TESTS = (
    "simple add addi and andi auipc beq bge bgeu blt bltu bne jal jalr lb lbu lh "
    "lhu lw ld_st lui or ori sb sh sw st_ld sll slli slt slti sltiu sltu "
    "sra srai srl srli sub xor xori"
).split()
# riscv-tests' ma_data exercises LH/LW crossing byte and word boundaries.
# Misaligned memory accesses are explicitly outside specs/cpu.md's RV32I scope.
RV32M_TESTS = "div divu mul mulh mulhsu mulhu rem remu".split()
ISA_PROFILES = {
    "rv32i": [("rv32ui", name) for name in RV32I_TESTS],
    "rv32im": [("rv32ui", name) for name in RV32I_TESTS] + [("rv32um", name) for name in RV32M_TESTS],
}


def _json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _compiler() -> str | None:
    return next((name for name in ("riscv32-unknown-elf-gcc", "riscv64-unknown-elf-gcc")
                 if shutil.which(name)), None)


def _errors(text: str) -> list[dict[str, object]]:
    found = []
    for path, line, column, message in re.findall(r"([^\n:]+\.vhd):([0-9]+):([0-9]+):(?:error:)?\s*(.+)", text):
        found.append({"file": path, "line": int(line), "column": int(column), "message": message})
    return found[:20]


def _build_program(source: Path, tests: Path, output: Path, compiler: str, isa: str) -> tuple[bool, str]:
    env = Path(__file__).resolve().parent.parent / "env"
    macros = tests / "isa" / "macros" / "scalar"
    linker = Path(__file__).resolve().parent.parent / "link-zero.ld"
    command = [compiler, f"-march={isa}", "-mabi=ilp32", "-static", "-nostdlib", "-nostartfiles",
               f"-I{env}", f"-I{macros}", f"-T{linker}", str(source), "-o", str(output)]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.returncode == 0, result.stdout


def _official_cases(source: Path) -> dict[int, dict[str, object]]:
    """Map upstream TEST_* macro ids back to a source line for repair prompts."""
    found: dict[int, dict[str, object]] = {}
    seen: set[Path] = set()
    def visit(path: Path) -> None:
        if path in seen or not path.is_file():
            return
        seen.add(path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines, 1):
            match = re.search(r"\b(TEST_[A-Z0-9_]+)\s*\(\s*([0-9]+)", line)
            if match:
                item: dict[str, object] = {"macro": match.group(1), "source": str(path), "line": number,
                                           "invocation": line.strip(),
                                           "source_context": "\n".join(lines[max(0, number - 3):number + 2])}
                # The common scalar macros carry all data needed to diagnose a
                # wrong ALU result directly in their invocation.
                args = [part.strip() for part in line[line.find("(") + 1:line.rfind(")")].split(",")]
                if match.group(1) == "TEST_RR_OP" and len(args) >= 5:
                    item["meaning"] = (f"Execute `{args[1]}` with rs1={args[3]} and rs2={args[4]}; "
                                       f"the destination register must equal {args[2]}.")
                elif match.group(1) == "TEST_IMM_OP" and len(args) >= 5:
                    item["meaning"] = (f"Execute `{args[1]}` with rs1={args[3]} and immediate={args[4]}; "
                                       f"the destination register must equal {args[2]}.")
                found[int(match.group(2))] = item
            include = re.search(r'#include\s+"([^"]+\.S)"', line)
            if include:
                visit((path.parent / include.group(1)).resolve())
    visit(source.resolve())
    return found


def _run_one(runner, sources: list[Path], program: Path, name: str, out: Path, max_cycles: int,
             *, waves: bool = False, full_trace: bool = False) -> dict:
    from cocotb_tools.runner import VHDL

    case_dir = out / name
    case_dir.mkdir(parents=True, exist_ok=True)
    report = case_dir / "report.json"
    log = case_dir / "sim.log"
    config = case_dir / "config.json"
    trace = case_dir / "trace.json"
    vcd = case_dir / "wave.vcd"
    _json(config, {"elf": str(program), "test": name, "max_cycles": max_cycles,
                   "report": str(report), "trace": str(trace) if full_trace else None})
    env = dict(os.environ)
    project_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = project_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        runner.test(hdl_toplevel="cpu", hdl_toplevel_lang="vhdl", test_module="spec_riscv_test.tb_riscv",
                    build_dir=out / "build", test_args=["--std=08"],
                    plusargs=[f"--vcd={vcd}"] if waves else [],
                    extra_env={**env, "SPEC_RISCV_TEST_CONFIG": str(config)}, log_file=log)
    except BaseException as error:  # Cocotb's runner uses different exception types by release.
        if not report.exists():
            return {"status": "failed", "test": name, "kind": "simulation_error", "message": str(error),
                    "log": str(log)}
    if not report.exists():
        return {"status": "failed", "test": name, "kind": "missing_report",
                "message": "a simulação terminou sem report.json; trate como reprovação", "log": str(log)}
    data = json.loads(report.read_text(encoding="utf-8"))
    data["kind"] = "program" if data["status"] == "failed" else "pass"
    data["log"] = str(log)
    if full_trace and trace.exists():
        data["trace_file"] = str(trace)
    if waves and vcd.exists():
        data["vcd"] = str(vcd)
    return data


def run(args: argparse.Namespace) -> dict:
    cpu, tests, out = Path(args.cpu).resolve(), Path(args.riscv_tests).resolve(), Path(args.out).resolve()
    report_path = out / "report.json"
    try:
        validate_top(cpu)
        sources = sources_for(cpu)
    except ValueError as error:
        result = {"status": "failed", "kind": "cpu_contract", "message": str(error), "fix": "Ajuste src/cpu.vhd para specs/cpu.md."}
        _json(report_path, result)
        return result
    # Compile first: an invalid CPU must be diagnosed even on a machine that
    # has not yet installed the RISC-V cross compiler.
    try:
        from cocotb_tools.runner import VHDL, get_runner
        runner = get_runner("ghdl")
        runner.build(sources=[VHDL(source) for source in sources], hdl_toplevel="cpu",
                     build_dir=out / "build", always=True, build_args=["--std=08"],
                     log_file=out / "compile.log")
    except BaseException as error:
        text = (out / "compile.log").read_text(encoding="utf-8", errors="replace") if (out / "compile.log").exists() else str(error)
        result = {"status": "failed", "kind": "vhdl_compile", "message": "GHDL não compilou a CPU", "errors": _errors(text), "log": str(out / "compile.log"), "fix": "Corrija primeiro os erros de sintaxe/tipo apontados em errors."}
        _json(report_path, result)
        return result
    compiler = _compiler()
    if compiler is None:
        result = {"status": "failed", "kind": "environment", "message": "compilador RISC-V não encontrado", "fix": "Instale riscv32-unknown-elf-gcc ou riscv64-unknown-elf-gcc e execute novamente."}
        _json(report_path, result)
        return result
    available = ISA_PROFILES[args.isa]
    requested = [item.strip() for item in args.tests.split(",") if item.strip()] if args.tests else [name for _, name in available]
    invalid = sorted(set(requested) - {name for _, name in available})
    if invalid:
        result = {"status": "failed", "kind": "selection", "message": f"testes não suportados para {args.isa}: {', '.join(invalid)}", "available": [name for _, name in available]}
        _json(report_path, result)
        return result
    programs = out / "programs"
    programs.mkdir(parents=True, exist_ok=True)
    built: list[tuple[str, str, Path]] = []
    for suite, name in available:
        if name not in requested:
            continue
        source = tests / "isa" / suite / f"{name}.S"
        label = f"{suite}-p-{name}"
        target = programs / label
        if not source.is_file():
            result = {"status": "failed", "kind": "environment", "message": f"fonte oficial ausente: {source}", "fix": "Confira --riscv-tests."}
            _json(report_path, result)
            return result
        ok, log = _build_program(source, tests, target, compiler, args.isa)
        (programs / f"{label}.build.log").write_text(log, encoding="utf-8")
        if not ok:
            result = {"status": "failed", "kind": "program_build", "test": label, "message": "o compilador não gerou o ELF oficial", "log": str(programs / f"{label}.build.log")}
            _json(report_path, result)
            return result
        try:
            image = load(target)
        except ElfError as error:
            result = {"status": "failed", "kind": "elf", "test": name, "message": str(error)}
            _json(report_path, result)
            return result
        if image.entry != 0 or "tohost" not in image.symbols:
            result = {"status": "failed", "kind": "elf_contract", "test": name,
                      "message": "ELF incompatível: entrada deve ser 0 e símbolo tohost deve existir", "entry": hex(image.entry), "symbols": sorted(image.symbols)}
            _json(report_path, result)
            return result
        built.append((suite, label, target))
    outcomes = []
    for suite, label, program in built:
        outcome = _run_one(runner, sources, program, label, out, args.max_cycles,
                           waves=args.waves, full_trace=args.full_trace)
        case = outcome.get("test_case")
        if isinstance(case, int):
            name = label.removeprefix(f"{suite}-p-")
            hint = _official_cases(tests / "isa" / suite / f"{name}.S").get(case)
            if hint:
                outcome["official_case"] = hint
        outcomes.append(outcome)
    failed = [item for item in outcomes if item["status"] != "passed"]
    result = {"status": "passed" if not failed else "failed", "suite": f"riscv-tests {args.isa}", "isa": args.isa, "cpu": str(cpu), "executed": len(outcomes), "passed": len(outcomes) - len(failed), "failed": len(failed), "results": outcomes,
              "next_action": "A CPU passou todos os programas selecionados." if not failed else "Corrija o primeiro resultado reprovado; o PC e o ciclo reproduzem o ponto observado."}
    _json(report_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Executa riscv-tests RV32UI numa CPU que segue specs/cpu.md")
    parser.add_argument("--cpu", required=True, help="diretório da CPU, com src/cpu.vhd")
    parser.add_argument("--riscv-tests", required=True, help="clone do riscv-tests")
    parser.add_argument("--out", default="spec-riscv-test/out", help="diretório de relatórios")
    parser.add_argument("--tests", help="lista CSV de testes rv32ui; padrão: toda a seleção RV32I suportada")
    parser.add_argument("--isa", choices=sorted(ISA_PROFILES), default="rv32i", help="perfil ISA: rv32i ou rv32im")
    parser.add_argument("--max-cycles", type=int, default=20_000)
    parser.add_argument("--waves", action="store_true", help="grava VCD da execução Cocotb oficial")
    parser.add_argument("--full-trace", action="store_true", help="grava traço público completo por ciclo")
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
