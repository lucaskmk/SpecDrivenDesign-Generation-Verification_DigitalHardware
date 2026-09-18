#!/usr/bin/env python3
# REQ: FR-RV-41 -- wrapper unico do fluxo Quartus (sintese+fit+timing via
# --flow compile, depois potencia, depois Fmax), grava
# quartus_output/{compilation,reports,netlist,bitstream}/ e summary.json.
#
# Roda DENTRO do container quartus-lite (docker/Quartus_Dockerfile), nunca
# no host: assume que quartus_map/quartus_fit/quartus_sh/quartus_sta/
# quartus_pow estao no PATH. Formatos de relatorio (fit.summary,
# pow.summary, sta.summary, saida de report_clock_fmax_summary) foram
# conferidos contra execucao real do Quartus 25.1std.0.1129 em
# docker/quartus_smoketest/ (specs/tasks.md, TRV-8.3 a TRV-8.6) antes de
# escrever os parsers abaixo -- nao foram adivinhados da documentacao.
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FMAX_TCL_TEMPLATE = """\
project_open {revision} -revision {revision}
create_timing_netlist
read_sdc
update_timing_netlist
report_clock_fmax_summary -panel_name Fmax -stdout
"""

NO_SDC_MARKER = "Synopsys Design Constraints File file not found"


def run_logged(cmd, log_path, cwd):
    with open(log_path, "w") as f:
        proc = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, log_path.read_text(errors="replace")


def parse_kv_report(text):
    """Um relatorio Quartus .summary e uma lista de 'Chave : valor' -- usado
    por fit.summary e pow.summary, que tem shape identico apesar do
    conteudo diferente."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(.+?)\s*:\s*(.+)$", line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def parse_used_total_percent(value):
    """'3 / 18,480 ( < 1 % )' -> (3, 18480, 1.0, '<'). O Quartus usa '<'/'>'
    pra faixas apertadas -- descartar o qualificador faria "< 1 %" virar
    "1 %" no JSON, uma afirmacao mais precisa do que a ferramenta realmente
    deu, exatamente o tipo de coisa que NFR-RV-02 probe."""
    m = re.match(r"([\d,]+)\s*/\s*([\d,]+)\s*\(\s*([<>]?)\s*([\d.]+)\s*%\s*\)", value)
    if not m:
        return None, None, None, None
    used = int(m.group(1).replace(",", ""))
    total = int(m.group(2).replace(",", ""))
    qualifier = m.group(3) or None
    pct = float(m.group(4))
    return used, total, pct, qualifier


def parse_mw(value):
    m = re.match(r"([\d.]+)\s*mW", value)
    return float(m.group(1)) if m else None


def parse_fit_summary(text):
    kv = parse_kv_report(text)
    result = {"device": kv.get("Device"), "status": kv.get("Fitter Status", "").split(" - ")[0]}
    used, total, pct, qualifier = parse_used_total_percent(kv.get("Logic utilization (in ALMs)", ""))
    result["logic_alms_used"], result["logic_alms_total"] = used, total
    result["logic_utilization_percent"] = pct
    result["logic_utilization_percent_qualifier"] = qualifier
    result["registers"] = int(kv["Total registers"]) if "Total registers" in kv else None
    used, total, _, _ = parse_used_total_percent(kv.get("Total pins", ""))
    result["pins_used"], result["pins_total"] = used, total
    used, total, _, _ = parse_used_total_percent(kv.get("Total block memory bits", ""))
    result["block_memory_bits_used"], result["block_memory_bits_total"] = used, total
    used, total, _, _ = parse_used_total_percent(kv.get("Total DSP Blocks", ""))
    result["dsp_blocks_used"], result["dsp_blocks_total"] = used, total
    used, total, _, _ = parse_used_total_percent(kv.get("Total PLLs", ""))
    result["plls_used"], result["plls_total"] = used, total
    result["fits"] = result["status"] == "Successful"
    return result


def parse_pow_summary(text):
    kv = parse_kv_report(text)
    return {
        "device": kv.get("Device"),
        "status": kv.get("Power Analyzer Status", "").split(" - ")[0],
        "total_mw": parse_mw(kv.get("Total Thermal Power Dissipation", "")),
        "core_dynamic_mw": parse_mw(kv.get("Core Dynamic Thermal Power Dissipation", "")),
        "core_static_mw": parse_mw(kv.get("Core Static Thermal Power Dissipation", "")),
        "io_mw": parse_mw(kv.get("I/O Thermal Power Dissipation", "")),
        "confidence": kv.get("Power Estimation Confidence"),
        "estimate": True,
    }


def parse_sta_summary(text):
    """Blocos repetidos 'Type : <corner> Model <Setup|Hold|...> <clk>' /
    'Slack : x.xxx' / 'TNS : x.xxx'. Pior caso = menor slack de cada
    categoria, entre todos os corners -- e assim que o proprio Quartus
    define "worst-case" no log do --flow compile."""
    entries = re.findall(
        r"Type\s*:\s*(.+?)\n\s*Slack\s*:\s*(-?[\d.]+)", text
    )
    worst_setup = None
    worst_hold = None
    for kind, slack in entries:
        slack = float(slack)
        if "Setup" in kind:
            worst_setup = slack if worst_setup is None else min(worst_setup, slack)
        elif "Hold" in kind:
            worst_hold = slack if worst_hold is None else min(worst_hold, slack)
    closure = None
    if worst_setup is not None and worst_hold is not None:
        closure = worst_setup >= 0 and worst_hold >= 0
    return {"worst_setup_slack_ns": worst_setup, "worst_hold_slack_ns": worst_hold, "closure": closure}


def parse_fmax_log(text):
    m = re.search(r"([\d.]+)\s*MHz\s+([\d.]+)\s*MHz\s+(\S+)", text)
    if not m:
        return {"fmax_mhz": None, "restricted_fmax_mhz": None, "clock": None}
    return {"fmax_mhz": float(m.group(1)), "restricted_fmax_mhz": float(m.group(2)), "clock": m.group(3)}


def analyze(project, revision, workdir, output_dir):
    workdir = Path(workdir)
    output_dir = Path(output_dir)
    compilation_dir = output_dir / "compilation"
    reports_dir = output_dir / "reports"
    netlist_dir = output_dir / "netlist"
    bitstream_dir = output_dir / "bitstream"
    for d in (compilation_dir, reports_dir, netlist_dir, bitstream_dir):
        d.mkdir(parents=True, exist_ok=True)

    summary = {"project": project, "revision": revision, "device": None}

    compile_log = compilation_dir / "compile.log"
    rc, compile_text = run_logged(
        ["quartus_sh", "--flow", "compile", project, "-c", revision], compile_log, workdir
    )
    summary["compilation"] = {"success": rc == 0, "log": str(compile_log.relative_to(output_dir.parent))}
    constrained = NO_SDC_MARKER not in compile_text

    if rc != 0:
        # FR-RV-41: falha que impede analise -- nao roda fit/timing/potencia
        # com uma compilacao invalida por baixo.
        summary["fit"] = None
        summary["timing"] = None
        summary["power"] = None
        summary["bitstream"] = {"preserved": False, "path": None}
        (reports_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        return 1, summary

    output_files_dir = workdir / "output_files"

    fit_summary_path = output_files_dir / f"{revision}.fit.summary"
    fit = parse_fit_summary(fit_summary_path.read_text()) if fit_summary_path.exists() else {"fits": False}
    summary["device"] = fit.get("device")
    summary["fit"] = fit
    (reports_dir / "resources.json").write_text(json.dumps(fit, indent=2))

    sta_summary_path = output_files_dir / f"{revision}.sta.summary"
    sta = parse_sta_summary(sta_summary_path.read_text()) if sta_summary_path.exists() else {}
    fmax_log = compilation_dir / "fmax.log"
    fmax_tcl = workdir / f"_analyze_fmax_{revision}.tcl"
    fmax_tcl.write_text(FMAX_TCL_TEMPLATE.format(revision=revision))
    _, fmax_text = run_logged(["quartus_sta", "-t", fmax_tcl.name], fmax_log, workdir)
    fmax_tcl.unlink(missing_ok=True)
    fmax = parse_fmax_log(fmax_text)
    timing = {
        "constrained": constrained,
        "reliable": constrained,
        **sta,
        **fmax,
        "log": str(fmax_log.relative_to(output_dir.parent)),
    }
    summary["timing"] = timing
    (reports_dir / "timing.json").write_text(json.dumps(timing, indent=2))

    pow_log = compilation_dir / "power.log"
    rc_pow, _ = run_logged(["quartus_pow", project, "-c", revision], pow_log, workdir)
    pow_summary_path = output_files_dir / f"{revision}.pow.summary"
    power = parse_pow_summary(pow_summary_path.read_text()) if pow_summary_path.exists() else {"estimate": True}
    summary["power"] = power
    (reports_dir / "power.json").write_text(json.dumps(power, indent=2))

    sof_path = output_files_dir / f"{revision}.sof"
    if fit.get("fits") and sof_path.exists():
        shutil.copy2(sof_path, bitstream_dir / sof_path.name)
        summary["bitstream"] = {"preserved": True, "path": str((bitstream_dir / sof_path.name).relative_to(output_dir.parent))}
    else:
        summary["bitstream"] = {"preserved": False, "path": None}

    map_rpt = output_files_dir / f"{revision}.map.rpt"
    if map_rpt.exists():
        shutil.copy2(map_rpt, netlist_dir / map_rpt.name)

    (reports_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    overall_ok = bool(fit.get("fits")) and rc_pow == 0
    return 0 if overall_ok else 1, summary


def main():
    parser = argparse.ArgumentParser(prog="quartus-analyze")
    parser.add_argument("--project", required=True, help="Nome do projeto Quartus (sem .qpf)")
    parser.add_argument("--revision", default=None, help="Default: mesmo nome do --project")
    parser.add_argument("--workdir", default="/workspace")
    parser.add_argument("--output", default=None, help="Default: <workdir>/quartus_output")
    args = parser.parse_args()

    project = args.project[:-4] if args.project.endswith(".qpf") else args.project
    revision = args.revision or project
    output_dir = args.output or str(Path(args.workdir) / "quartus_output")

    rc, summary = analyze(project, revision, args.workdir, output_dir)
    print(json.dumps(summary, indent=2))
    sys.exit(rc)


if __name__ == "__main__":
    main()
