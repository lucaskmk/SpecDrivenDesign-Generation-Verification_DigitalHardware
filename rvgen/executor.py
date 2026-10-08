#!/usr/bin/env python3
"""Executa ``spec-riscv-test`` como validador final externo.

REQ: FR-RV-49 (o veredito vem sempre do spec-riscv-test real), NFR-RV-07 (o gerador
chama o validador como SUBPROCESSO; nunca o importa para julgar uma CPU).

O modo final é local: executa o ambiente virtual de ``spec-riscv-test`` e
requer GHDL, compilador RISC-V e o clone upstream. O resultado vem sempre de
``<out>/report.json``, nunca da saída textual.
"""

from __future__ import annotations

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

TESTADOR_PADRAO = REPO_ROOT / "spec-riscv-test" / ".venv" / "bin" / "spec-riscv-test"
RISCV_TESTS_PADRAO = REPO_ROOT / "riscv-tests"


class ErroExecutor(RuntimeError):
    """Nao ha onde rodar o validador, ou a entrega esta fora do repositorio."""


@dataclass(frozen=True)
class Execucao:
    """Uma execução do validador externo sobre uma entrega."""

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
    """Lê o JSON estável emitido pelo validador externo."""
    if not caminho.is_file():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if isinstance(dados, list):
        return dados[0] if dados and isinstance(dados[0], dict) else None
    return dados if isinstance(dados, dict) else None


class Executor:
    """Base: monta o comando e roda; as subclasses so decidem o comando."""

    nome = "?"

    def __init__(self, raiz: Path = REPO_ROOT) -> None:
        self.raiz = Path(raiz).resolve()

    def comando(self, pasta: Path, *, json_saida: Path, workdir: Path,
                build_root: Path, casos: list[str] | None = None,
                etapa: str = "rv32i", ondas: bool = False,
                traco_completo: bool = False) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError

    def rodar(self, pasta: Path, *, json_saida: Path, workdir: Path,
                build_root: Path, casos: list[str] | None = None,
                etapa: str = "rv32i", timeout: float = 3600.0,
                ondas: bool = False, traco_completo: bool = False) -> Execucao:
        opcoes = {"ondas": ondas, "traco_completo": traco_completo} if (ondas or traco_completo) else {}
        cmd, env_extra = self.comando(pasta, json_saida=json_saida,
                                       workdir=workdir, build_root=build_root,
                                       casos=casos, etapa=etapa, **opcoes)
        return self._rodar_comando(cmd, json_saida, workdir, build_root, timeout,
                                   env_extra=env_extra)

    def _rodar_comando(self, cmd: list[str], json_saida: Path, workdir: Path,
                       build_root: Path, timeout: float,
                       *, env_extra: dict[str, str] | None = None) -> Execucao:
        """Executa um comando que grava um relatorio JSON estruturado."""
        json_saida.parent.mkdir(parents=True, exist_ok=True)
        json_saida.unlink(missing_ok=True)       # nunca ler o relatorio de ontem
        workdir.mkdir(parents=True, exist_ok=True)
        build_root.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.update(env_extra or {})
        inicio = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=self.raiz, env=env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=timeout)
            codigo, saida = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            codigo, saida = -1, f"spec-riscv-test excedeu o limite de {timeout:.0f} s"
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

    def rodar_componente(self, pasta: Path, *, componente: str, teste: Path,
                          json_saida: Path, workdir: Path, build_root: Path,
                          fontes: list[Path] | None = None,
                          vcd: Path | None = None,
                          timeout: float = 3600.0) -> Execucao:
        """Executa um testbench de componente no ambiente do gerador."""
        raise NotImplementedError


class ExecutorLocal(Executor):
    """Invoca o ambiente isolado de ``spec-riscv-test`` no host."""

    nome = "local"

    def __init__(self, raiz: Path = REPO_ROOT, *, testador: Path | None = None,
                 riscv_tests: Path | None = None) -> None:
        super().__init__(raiz)
        self.testador = Path(testador or os.environ.get("RVGEN_SPEC_RISCV_TEST") or
                             TESTADOR_PADRAO).resolve()
        self.riscv_tests = Path(riscv_tests or os.environ.get("RVGEN_RISCV_TESTS") or
                                RISCV_TESTS_PADRAO).resolve()

    def comando(self, pasta: Path, *, json_saida: Path, workdir: Path,
                build_root: Path, casos: list[str] | None = None,
                etapa: str = "rv32i", ondas: bool = False,
                traco_completo: bool = False) -> tuple[list[str], dict[str, str]]:
        # A API do wrapper grava invariavelmente ``<out>/report.json``.
        cmd = [str(self.testador), "--cpu", str(pasta), "--riscv-tests",
               str(self.riscv_tests), "--out", str(json_saida.parent), "--isa", etapa]
        if casos:
            nomes = []
            for caso in casos:
                nome = caso.rsplit("/", 1)[-1]
                nomes.append(nome.rsplit("-p-", 1)[-1])
            cmd += ["--tests", ",".join(nomes)]
        if ondas:
            cmd.append("--waves")
        if traco_completo:
            cmd.append("--full-trace")
        return cmd, {}

    def rodar_componente(self, pasta, *, componente, teste, json_saida, workdir,
                           build_root, fontes=None, vcd=None, timeout=3600.0):
        # Os testes auxiliares precisam do mesmo cocotb_tools instalado pelo
        # wrapper oficial, não necessariamente do Python que iniciou rvgen.
        python_testador = self.testador.parent / "python"
        cmd = [str(python_testador), "-m", "rvgen.component_runner", "--cpu",
                str(pasta), "--component", componente,
               "--test", str(teste), "--json", str(json_saida),
               "--workdir", str(workdir), "--build-root", str(build_root)]
        for fonte in fontes or []:
            cmd += ["--source", str(fonte)]
        if vcd:
            cmd += ["--vcd", str(vcd)]
        return self._rodar_comando(cmd, json_saida, workdir, build_root, timeout)


class ExecutorDocker(Executor):
    """Mantido apenas para testes de componente em imagens legadas."""

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
                etapa: str = "rv32i", ondas: bool = False,
                traco_completo: bool = False) -> tuple[list[str], dict[str, str]]:
        raise ErroExecutor("spec-riscv-test e executado localmente; use --executor local")

    def rodar_componente(self, pasta, *, componente, teste, json_saida, workdir,
                          build_root, fontes=None, vcd=None, timeout=3600.0):
        # Arquivos de build incluem __pycache__ criado pelo Python do cocotb.
        # Rodar como o usuario do host preserva a limpeza da sessao e dos testes
        # de integracao, em vez de deixa-los pertencentes ao root do container.
        usuario = f"{os.getuid()}:{os.getgid()}"
        cmd = ["docker", "run", "--rm", "--user", usuario,
               "-v", f"{self.raiz}:/job", "-w", "/job",
               self.imagem, "python3", "-m", "rvgen.component_runner", "--cpu",
               self._no_container(Path(pasta)), "--component", componente,
               "--test", self._no_container(teste), "--json", self._no_container(json_saida),
               "--workdir", self._no_container(workdir), "--build-root",
               self._no_container(build_root)]
        for fonte in fontes or []:
            cmd += ["--source", self._no_container(fonte)]
        if vcd:
            cmd += ["--vcd", self._no_container(vcd)]
        return self._rodar_comando(cmd, json_saida, workdir, build_root, timeout)


# --------------------------------------------------------------------------
# disponibilidade
# --------------------------------------------------------------------------

Which = Callable[[str], str | None]
Runner = Callable[..., subprocess.CompletedProcess]


def checar_local(which: Which = shutil.which,
                  tem_modulo: Callable[[str], bool] | None = None) -> Disponibilidade:
    """Pré-requisitos do wrapper oficial, sem importar seu ambiente virtual."""
    faltando = []
    if not which("ghdl"):
        faltando.append("ghdl nao esta no PATH")
    testador = Path(os.environ.get("RVGEN_SPEC_RISCV_TEST") or TESTADOR_PADRAO)
    riscv_tests = Path(os.environ.get("RVGEN_RISCV_TESTS") or RISCV_TESTS_PADRAO)
    if not testador.is_file() or not os.access(testador, os.X_OK):
        faltando.append(f"spec-riscv-test nao executavel em {testador}")
    if not (riscv_tests / "isa").is_dir():
        faltando.append(f"riscv-tests ausente em {riscv_tests}")
    if not (which("riscv32-unknown-elf-gcc") or which("riscv64-unknown-elf-gcc")):
        faltando.append("compilador RISC-V nao esta no PATH")
    if faltando:
        return Disponibilidade(
            False, "; ".join(faltando),
            "instale spec-riscv-test/.venv, clone riscv-tests ao lado do repositorio "
            "ou defina RVGEN_SPEC_RISCV_TEST e RVGEN_RISCV_TESTS",
        )
    return Disponibilidade(True, f"spec-riscv-test e toolchain RISC-V no host ({testador})")


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
    """A suíte oficial requer ambiente local; Docker não é um fallback final."""
    local = local or checar_local
    docker = docker or (lambda: checar_docker(imagem))
    if preferencia == "local":
        d = local()
        if not d.pronto:
            raise ErroExecutor(f"executor local indisponivel: {d.detalhe}. "
                               f"Resolver: {d.como_resolver}")
        return ExecutorLocal()
    if preferencia == "docker":
        raise ErroExecutor("spec-riscv-test nao esta instalado na imagem Docker; use --executor local")
    if preferencia != "auto":
        raise ErroExecutor(f"executor {preferencia!r} desconhecido; use auto, local ou docker")
    dl = local()
    if dl.pronto:
        return ExecutorLocal()
    raise ErroExecutor(
        "nao ha onde rodar spec-riscv-test:\n"
        f"  local : {dl.detalhe} -> {dl.como_resolver}"
    )
