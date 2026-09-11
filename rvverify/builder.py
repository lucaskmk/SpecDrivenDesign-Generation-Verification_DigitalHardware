#!/usr/bin/env python3
"""Compilacao e execucao do design descrito por um `cpu.toml`.

REQ: FR-RV-21 (execucao real com exit code), NFR-RV-01 (GHDL + cocotb),
NFR-RV-02 (nada e declarado sem rodar a ferramenta).

Duas responsabilidades, e so duas:

  * `build_design`   -- analisa as fontes do manifesto, na ordem declarada,
                        uma unica vez por arvore de fontes (cache por hash);
  * `run_simulation` -- dispara `ghdl -r` via `cocotb_tools.runner`, com os
                        generics do manifesto sobrepostos pelos da chamada.

Por que o cache: o GHDL aplica generics na ELABORACAO, que no backend mcode
acontece em `ghdl -r`. Compilar uma vez e elaborar por caso de teste e a
diferenca entre uma suite de 3 minutos e uma de meia hora.

Aviso operacional: dois processos GHDL escrevendo na MESMA biblioteca a
corrompem. Rode cada agente/suite paralela com `RV_BUILD_ROOT` proprio.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cocotb_tools.runner import VHDL, get_results, get_runner

from .manifest import CpuManifest

__all__ = [
    "SimulationFailed",
    "BuiltDesign",
    "build_design",
    "run_simulation",
    "design_declares_generic",
    "build_root",
    "sources_stamp",
]

# Raiz dos builds. Fica no filesystem do WSL de proposito: compilar dentro de
# /mnt/c e significativamente mais lento.
_DEFAULT_BUILD_ROOT = Path.home() / "rv32_build_cache"

# (chave de fontes) -> (build_dir, runner). O runner e reaproveitado porque
# `cocotb_tools.runner` guarda nele o estado das fontes definido em `build()`,
# exigido depois por `test()`.
_build_cache: dict[tuple, "BuiltDesign"] = {}
_top_source_cache: dict[tuple, Path | None] = {}
_generic_cache: dict[tuple, bool] = {}


def build_root() -> Path:
    """Raiz dos diretorios de build, configuravel por variavel de ambiente."""
    env = os.environ.get("RVVERIFY_BUILD_ROOT") or os.environ.get("RV_BUILD_ROOT")
    return Path(env) if env else _DEFAULT_BUILD_ROOT


def sources_stamp(sources: list[Path]) -> str:
    """Impressao digital da arvore de fontes (nome, tamanho, mtime)."""
    h = hashlib.sha256()
    for p in sources:
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:16]


@dataclass
class BuiltDesign:
    """Um design ja analisado pelo GHDL, pronto para elaborar."""

    manifest: CpuManifest
    build_dir: Path
    runner: Any
    sources: list[Path]
    stamp: str

    @property
    def toplevel(self) -> str:
        """Nome do top como o GHDL o registra na biblioteca (minusculas)."""
        return self.manifest.design.top.lower()


def build_design(manifest: CpuManifest, *, src_dir: Path | None = None,
                 build_dir: Path | None = None) -> BuiltDesign:
    """Analisa as fontes do manifesto e devolve o build (com cache).

    `src_dir` troca a arvore de fontes mantendo a ordem de analise do
    manifesto -- e o que permite rodar o RTL original extraido do git sob o
    mesmo testbench, em vez de confiar num snapshot anotado a mao.
    """
    sources = manifest.source_paths(src_dir)
    stamp = sources_stamp(sources)
    key = (
        str(src_dir or manifest.root),
        manifest.design.top.lower(),
        manifest.design.std,
        stamp,
    )
    cached = _build_cache.get(key)
    if cached is not None and cached.build_dir.exists():
        return cached

    target = Path(build_dir) if build_dir else build_root() / f"build_{stamp}"
    target.mkdir(parents=True, exist_ok=True)

    runner = get_runner("ghdl")
    runner.build(
        sources=[VHDL(p) for p in sources],
        hdl_toplevel=manifest.design.top.lower(),
        build_args=[f"--std={manifest.design.std}"],
        build_dir=target,
        always=True,
    )
    built = BuiltDesign(manifest=manifest, build_dir=target, runner=runner,
                        sources=sources, stamp=stamp)
    _build_cache[key] = built
    return built


def _pythonpath(extra: list[Path]) -> str:
    """PYTHONPATH do processo do simulador.

    O modulo cocotb roda dentro do GHDL, num processo que NAO herda o
    `sys.path` do pytest -- so o PYTHONPATH. Sem a raiz do repositorio aqui,
    `import rvverify` falha la dentro com um traceback obscuro.
    """
    parts = [str(p) for p in extra]
    current = os.environ.get("PYTHONPATH", "")
    if current:
        parts.append(current)
    return os.pathsep.join(parts)


class SimulationFailed(AssertionError):
    """A simulacao rodou e REPROVOU. Distinta de um erro de ferramenta."""


def run_simulation(built: BuiltDesign, *, test_module: str,
                   parameters: dict[str, Any] | None = None,
                   extra_env: dict[str, str] | None = None,
                   python_paths: list[Path] | None = None,
                   waves: bool = False) -> Path:
    """Elabora e executa o design. Levanta excecao se o GHDL ou o teste falhar.

    `parameters` sao os generics da CHAMADA; eles VENCEM os declarados em
    [design.generics] (uma suite alterna configuracao caso a caso).

    ATENCAO -- por que a checagem do resultado e feita aqui, na mao:

    `cocotb_tools.runner.test()` so confere o XML de resultados quando detecta
    que esta rodando SOB PYTEST (ele olha a variavel de ambiente
    PYTEST_CURRENT_TEST). Fora do pytest -- que e exatamente o caso de
    `python -m rvverify` -- ele devolve o caminho do XML sem olhar, e uma
    simulacao REPROVADA retorna normalmente.

    Sem a checagem explicita abaixo, o validador aprovaria qualquer CPU cujo
    GHDL apenas nao travasse. Isso foi encontrado por teste de mutacao: SRA
    trocado por deslocamento logico passava com 15/15. Ver NFR-RV-02.
    """
    manifest = built.manifest
    env = dict(os.environ)
    env.update(extra_env or {})
    repo_paths = [Path(__file__).resolve().parent.parent]
    env["PYTHONPATH"] = _pythonpath((python_paths or []) + repo_paths)

    try:
        results = built.runner.test(
            hdl_toplevel=built.toplevel,
            hdl_toplevel_lang="vhdl",
            test_module=test_module,
            test_args=[f"--std={manifest.design.std}"],
            build_dir=built.build_dir,
            parameters=manifest.generics_for(parameters),
            extra_env=env,
            waves=waves,
        )
    except SystemExit as e:
        # SOB PYTEST o runner ja confere o XML e chama sys.exit(codigo).
        # FORA do pytest ele nao confere nada (ver docstring). Traduzir aqui
        # da um unico tipo de excecao para o mesmo evento nos dois contextos --
        # sem isto, quem chama precisaria tratar SystemExit em um caso e
        # SimulationFailed no outro, e esquecer um dos dois volta a produzir
        # aprovacao em vazio.
        raise SimulationFailed(
            f"a simulacao reprovou (exit code {e.code}); "
            f"ver o log do GHDL acima"
        ) from e

    # Sob pytest o runner ja teria saido com sys.exit; chegar aqui com falhas
    # so acontece fora do pytest, e e justamente o caminho do `python -m`.
    results_path = Path(results) if results else None
    if results_path is None or not results_path.exists():
        raise SimulationFailed(
            f"a simulacao nao produziu arquivo de resultados "
            f"({results_path}); trate como reprovacao, nunca como aprovacao"
        )

    total, failed = get_results(results_path)
    if failed:
        raise SimulationFailed(
            f"{failed} de {total} teste(s) reprovaram na simulacao "
            f"(resultados em {results_path})"
        )
    return results_path


# --------------------------------------------------------------------------
# inspecao do RTL
# --------------------------------------------------------------------------

def _top_source(manifest: CpuManifest, src_dir: Path | None = None) -> Path | None:
    """Arquivo que declara a entidade de topo, procurado pelo texto do RTL.

    O resultado e memorizado: esta funcao e chamada uma vez por caso de teste
    e varrer a arvore de fontes inteira toda vez custaria centenas de leituras
    de disco numa suite de centenas de programas.
    """
    top = manifest.design.top.lower()
    cache_key = (top, str(src_dir or manifest.root), manifest.design.sources)
    if cache_key in _top_source_cache:
        return _top_source_cache[cache_key]
    pattern = re.compile(rf"\bentity\s+{re.escape(top)}\s+is\b", re.IGNORECASE)
    for path in manifest.source_paths(src_dir, require_all=False):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if pattern.search(text):
            _top_source_cache[cache_key] = path
            return path
    _top_source_cache[cache_key] = None
    return None


def design_declares_generic(manifest: CpuManifest, generic_name: str,
                            src_dir: Path | None = None) -> bool:
    """Descobre se a entidade de topo declara o generic pedido.

    Serve para NAO passar ao GHDL um generic que o design nao tem -- e o que
    permite comparar uma versao antiga do RTL (sem o generic) contra a atual
    usando o mesmo manifesto.
    """
    top = manifest.design.top.lower()
    cache_key = (top, str(src_dir or manifest.root), manifest.design.sources,
                 generic_name.lower())
    if cache_key in _generic_cache:
        return _generic_cache[cache_key]

    path = _top_source(manifest, src_dir)
    if path is None:
        _generic_cache[cache_key] = False
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    start = text.find(f"entity {top} is")
    if start < 0:
        return False
    end = text.find(f"end {top}", start)
    if end < 0:
        end = text.find("end entity", start)
    head = text[start:end] if end > start else text[start:]
    found = generic_name.lower() in head
    _generic_cache[cache_key] = found
    return found


def clear_cache() -> None:
    """Esquece os builds em memoria (usado por teste do proprio pipeline)."""
    _build_cache.clear()
    _top_source_cache.clear()
    _generic_cache.clear()
