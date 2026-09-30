#!/usr/bin/env python3
"""Onde o `rvverify` roda: no host ou dentro da imagem `spechdl-toolchain`.

REQ: FR-RV-49 (o veredito vem sempre do rvverify real), NFR-RV-07 (o gerador
chama o validador como SUBPROCESSO; nunca o importa para julgar uma CPU).

Dois modos, a mesma chamada:

  * `local`  -- `python -m rvverify` no proprio host. Exige GHDL no PATH e
                cocotb importavel (Linux/WSL, ADR-006).
  * `docker` -- o mesmo comando dentro da imagem `spechdl-toolchain`, com o
                repositorio montado em /job. E o modo que permite, num host
                Windows, ter o Ollama nativo (com GPU) e o GHDL no container
                ao mesmo tempo (ADR-018).

Em qualquer modo o resultado e lido do `--json` que o proprio `rvverify`
grava -- nunca da saida de texto, que e para humanos. Cada entrega usa um
`RVVERIFY_BUILD_ROOT` proprio: dois GHDL escrevendo na mesma biblioteca a
corrompem (aviso de `rvverify/builder.py`).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from .config import IMAGEM_DOCKER_PADRAO, REPO_ROOT

__all__ = [
    "ErroExecutor",
    "Execucao",
    "Disponibilidade",
    "Executor",
    "ExecutorLocal",
    "ExecutorDocker",
    "checar_local",
    "checar_docker",
    "escolher_executor",
    "ler_relatorio",
    "IMAGEM_PUBLICADA",
]

# Tag publicada da mesma imagem (docker/README.md): puxar e mais rapido que
# buildar, e o nome local continua sendo o que o projeto usa.
IMAGEM_PUBLICADA = "gabrielgalazzi/imagens_projeto_descomp:spechdl-latest"

ETAPAS = ("rv32i", "rv32m", "ambas")


class ErroExecutor(RuntimeError):
    """Nao ha onde rodar o validador, ou a entrega esta fora do repositorio."""


@dataclass(frozen=True)
class Execucao:
    """Uma execucao do `rvverify` sobre uma entrega."""

    comando: list[str]
    codigo: int
    relatorio: dict | None
    saida: str
    segundos: float
    json_path: Path


@dataclass(frozen=True)
class Disponibilidade:
    """Se um modo de execucao esta pronto e, se nao estiver, o que fazer."""

    pronto: bool
    detalhe: str
    como_resolver: str | None = None


def ler_relatorio(caminho: Path) -> dict | None:
    """O relatorio da CPU no `--json` do rvverify (uma lista com um item)."""
    if not caminho.is_file():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if isinstance(dados, list):
        return dados[0] if dados and isinstance(dados[0], dict) else None
    return dados if isinstance(dados, dict) else None


def _filtros(casos: list[str] | None, etapa: str) -> list[str]:
    if etapa not in ETAPAS:
        raise ValueError(f"etapa {etapa!r} invalida; aceitas: {', '.join(ETAPAS)}")
    args: list[str] = []
    if etapa != "ambas":
        args += ["--etapa", etapa]
    if casos:
        args += ["--casos", ",".join(casos)]
    return args


class Executor:
    """Base: monta o comando e roda; as subclasses so decidem o comando."""

    nome = "?"

    def __init__(self, raiz: Path = REPO_ROOT) -> None:
        self.raiz = Path(raiz).resolve()

    def comando(self, pasta: Path, *, json_saida: Path, workdir: Path,
                build_root: Path, casos: list[str] | None = None,
                etapa: str = "ambas") -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError

    def rodar(self, pasta: Path, *, json_saida: Path, workdir: Path,
              build_root: Path, casos: list[str] | None = None,
              etapa: str = "ambas", timeout: float = 3600.0) -> Execucao:
        cmd, env_extra = self.comando(pasta, json_saida=json_saida,
                                      workdir=workdir, build_root=build_root,
                                      casos=casos, etapa=etapa)
        json_saida.parent.mkdir(parents=True, exist_ok=True)
        json_saida.unlink(missing_ok=True)       # nunca ler o relatorio de ontem
        workdir.mkdir(parents=True, exist_ok=True)
        build_root.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.update(env_extra)
        inicio = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=self.raiz, env=env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=timeout)
            codigo, saida = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            codigo, saida = -1, f"rvverify excedeu o limite de {timeout:.0f} s"
        except OSError as e:
            raise ErroExecutor(f"nao foi possivel executar {cmd[0]}: {e}") from None
        return Execucao(
            comando=cmd,
            codigo=codigo,
            relatorio=ler_relatorio(json_saida),
            saida=saida[-8000:],
            segundos=round(time.monotonic() - inicio, 1),
            json_path=json_saida,
        )


class ExecutorLocal(Executor):
    """`python -m rvverify` no host, com o mesmo interpretador do gerador."""

    nome = "local"

    def comando(self, pasta: Path, *, json_saida: Path, workdir: Path,
                build_root: Path, casos: list[str] | None = None,
                etapa: str = "ambas") -> tuple[list[str], dict[str, str]]:
        cmd = [sys.executable, "-m", "rvverify", str(pasta),
               "--json", str(json_saida), "--sem-cor", "--workdir", str(workdir)]
        return cmd + _filtros(casos, etapa), {"RVVERIFY_BUILD_ROOT": str(build_root)}


class ExecutorDocker(Executor):
    """O mesmo comando dentro da imagem, com o repositorio em /job."""

    nome = "docker"

    def __init__(self, imagem: str = IMAGEM_DOCKER_PADRAO,
                 raiz: Path = REPO_ROOT) -> None:
        super().__init__(raiz)
        self.imagem = imagem

    def _no_container(self, caminho: Path) -> str:
        try:
            rel = Path(caminho).resolve().relative_to(self.raiz)
        except ValueError:
            raise ErroExecutor(
                f"{caminho} esta fora do repositorio ({self.raiz}); no modo "
                f"docker so o repositorio e montado no container. Use uma "
                f"pasta como entregas/<nome>."
            ) from None
        return PurePosixPath(*rel.parts).as_posix() or "."

    def comando(self, pasta: Path, *, json_saida: Path, workdir: Path,
                build_root: Path, casos: list[str] | None = None,
                etapa: str = "ambas") -> tuple[list[str], dict[str, str]]:
        cmd = ["docker", "run", "--rm",
               "-v", f"{self.raiz}:/job", "-w", "/job",
               "-e", f"RVVERIFY_BUILD_ROOT=/job/{self._no_container(build_root)}",
               self.imagem,
               "python3", "-m", "rvverify", self._no_container(pasta),
               "--json", self._no_container(json_saida), "--sem-cor",
               "--workdir", self._no_container(workdir)]
        return cmd + _filtros(casos, etapa), {}


# --------------------------------------------------------------------------
# disponibilidade
# --------------------------------------------------------------------------

Which = Callable[[str], str | None]
Runner = Callable[..., subprocess.CompletedProcess]


def checar_local(which: Which = shutil.which,
                 tem_modulo: Callable[[str], bool] | None = None) -> Disponibilidade:
    """GHDL no PATH e cocotb importavel por ESTE interpretador."""
    if tem_modulo is None:
        def tem_modulo(nome: str) -> bool:
            return importlib.util.find_spec(nome) is not None
    faltando = []
    if not which("ghdl"):
        faltando.append("ghdl nao esta no PATH")
    if not tem_modulo("cocotb_tools"):
        faltando.append(f"cocotb nao esta instalado em {sys.executable}")
    if faltando:
        return Disponibilidade(
            False, "; ".join(faltando),
            "no Linux/WSL: instale GHDL e `pip install cocotb` (ADR-006), "
            "ou use o modo docker",
        )
    return Disponibilidade(True, f"GHDL e cocotb no host ({sys.executable})")


def checar_docker(imagem: str = IMAGEM_DOCKER_PADRAO, which: Which = shutil.which,
                  run: Runner = subprocess.run) -> Disponibilidade:
    """Docker instalado, daemon respondendo e a imagem do validador presente."""
    if not which("docker"):
        return Disponibilidade(
            False, "Docker nao encontrado",
            "instale o Docker Desktop: https://docs.docker.com/get-docker/",
        )

    def _ok(args: list[str]) -> bool:
        try:
            return run(args, capture_output=True, text=True, timeout=30).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    if not _ok(["docker", "info", "--format", "{{.ServerVersion}}"]):
        return Disponibilidade(
            False, "o Docker esta instalado, mas o daemon nao responde",
            "abra o Docker Desktop (ou `sudo service docker start` no Linux)",
        )
    if not _ok(["docker", "image", "inspect", imagem]):
        return Disponibilidade(
            False, f"a imagem {imagem} nao existe neste Docker",
            f"docker pull {IMAGEM_PUBLICADA} && docker tag {IMAGEM_PUBLICADA} {imagem}"
            f"   (ou: docker build -t {imagem} docker/spechdl-toolchain)",
        )
    return Disponibilidade(True, f"imagem {imagem} no Docker")


def escolher_executor(preferencia: str = "auto", imagem: str = IMAGEM_DOCKER_PADRAO,
                      *, local: Callable[[], Disponibilidade] | None = None,
                      docker: Callable[[], Disponibilidade] | None = None) -> Executor:
    """O executor pedido, ou o primeiro pronto em `auto` (local, depois docker)."""
    local = local or checar_local
    docker = docker or (lambda: checar_docker(imagem))
    if preferencia == "local":
        d = local()
        if not d.pronto:
            raise ErroExecutor(f"executor local indisponivel: {d.detalhe}. "
                               f"Resolver: {d.como_resolver}")
        return ExecutorLocal()
    if preferencia == "docker":
        d = docker()
        if not d.pronto:
            raise ErroExecutor(f"executor docker indisponivel: {d.detalhe}. "
                               f"Resolver: {d.como_resolver}")
        return ExecutorDocker(imagem)
    if preferencia != "auto":
        raise ErroExecutor(f"executor {preferencia!r} desconhecido; use auto, local ou docker")
    dl = local()
    if dl.pronto:
        return ExecutorLocal()
    dd = docker()
    if dd.pronto:
        return ExecutorDocker(imagem)
    raise ErroExecutor(
        "nao ha onde rodar o rvverify:\n"
        f"  local : {dl.detalhe} -> {dl.como_resolver}\n"
        f"  docker: {dd.detalhe} -> {dd.como_resolver}"
    )
