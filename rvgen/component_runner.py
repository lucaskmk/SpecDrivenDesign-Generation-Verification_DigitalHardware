#!/usr/bin/env python3
"""Runner cocotb para um bloco gerado; etapa de depuracao, nao e veredito."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from cocotb_tools.runner import VHDL, get_results, get_runner


def _diagnostico(log: Path, limite: int = 6000) -> str:
    """Trecho final do log para a correcao, sem inchar o JSON/prompt."""
    try:
        texto = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return texto[-limite:]


def executar(cpu: Path, componente: str, teste: Path, *, workdir: Path,
             build_root: Path, fontes: list[Path] | None = None, vcd: Path | None = None) -> dict:
    # No Docker os argumentos chegam relativos a /job, mas o cocotb inicia o
    # Python a partir do diretorio de build. PYTHONPATH relativo apontaria para
    # o lugar errado e o modulo `test_<bloco>` nao seria importavel.
    cpu = cpu.resolve()
    teste = teste.resolve()
    workdir = workdir.resolve()
    build_root = build_root.resolve()
    if vcd:
        vcd = vcd.resolve()
        vcd.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    workdir.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)
    log = workdir / "sim.log"
    rel = {"component": componente, "testbench": str(teste),
           "compilacao": {"ok": False}, "passed": False, "detail": "", "log": str(log)}
    try:
        runner = get_runner("ghdl")
        sources = fontes or sorted((cpu / "src").glob("*.vhd")) + sorted((cpu / "src").glob("*.vhdl"))
        if not sources:
            raise ValueError(f"nenhuma fonte VHDL em {cpu / 'src'}")
        runner.build(sources=[VHDL(p) for p in sources],
                      hdl_toplevel=componente.lower(),
                      build_args=["--std=08"], build_dir=build_root,
                     always=True, log_file=log)
        rel["compilacao"]["ok"] = True
        env = dict(os.environ)
        raiz = Path(__file__).resolve().parent.parent
        env["PYTHONPATH"] = os.pathsep.join([str(teste.parent), str(raiz),
                                               os.environ.get("PYTHONPATH", "")])
        # O GHDL precisa executar na pasta de build, onde esta a biblioteca
        # `work` produzida acima. O cocotb 2.0 da imagem nao importou o modulo
        # somente via PYTHONPATH; disponibilizar uma copia no proprio build
        # preserva a biblioteca VHDL e torna `test_module` importavel.
        teste_no_build = build_root / teste.name
        shutil.copyfile(teste, teste_no_build)
        # Em GHDL, --vcd é argumento de simulação e deve vir após a unidade
        # top-level. cocotb posiciona `plusargs` nessa parte do comando.
        test_args = ["--std=08"]
        plusargs = [f"--vcd={vcd}"] if vcd else []
        resultado = runner.test(hdl_toplevel=componente.lower(), hdl_toplevel_lang="vhdl",
                                  test_module=teste.stem,
                                  test_args=test_args, build_dir=build_root,
                                 plusargs=plusargs, extra_env=env, log_file=log)
        xml = Path(resultado) if resultado else None
        if xml is None or not xml.exists():
            rel["detail"] = "a simulacao nao produziu resultados cocotb"
        else:
            total, falhos = get_results(xml)
            rel["passed"] = total > 0 and falhos == 0
            rel["detail"] = (f"{total} teste(s) aprovados" if rel["passed"]
                             else f"{falhos} de {total} teste(s) reprovaram")
    except BaseException as e:  # cocotb pode sinalizar falha com SystemExit
        rel["detail"] = f"{type(e).__name__}: {e}"
    diagnostico = _diagnostico(log)
    if diagnostico:
        rel["diagnostico"] = diagnostico
    rel["segundos"] = round(time.monotonic() - inicio, 1)
    if vcd and vcd.exists():
        rel["vcd"] = str(vcd)
    return rel


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", required=True)
    ap.add_argument("--component", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--build-root", required=True)
    ap.add_argument("--source", action="append", default=[],
                     help="fonte VHDL para este componente (repetivel)")
    ap.add_argument("--vcd", help="artefato VCD opcional da simulação")
    a = ap.parse_args(argv)
    rel = executar(Path(a.cpu), a.component, Path(a.test),
                  workdir=Path(a.workdir), build_root=Path(a.build_root),
                   fontes=[Path(p) for p in a.source] or None,
                   vcd=Path(a.vcd) if a.vcd else None)
    saida = Path(a.json)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(rel, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if rel["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
