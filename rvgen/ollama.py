#!/usr/bin/env python3
"""Ollama: achar, instalar, iniciar e abastecer com o modelo (`rvgen preparar`).

REQ: FR-RV-43 (verificar e reportar cada item), FR-RV-44 (instalar ou baixar
SO com confirmacao explicita), FR-RV-45 (iniciar `ollama serve` com log
proprio), FR-RV-46 (perfil de modelo pela memoria de video).

Este modulo so ACHA e FAZ; quem decide se pode fazer e o comando
`preparar` (`rvgen/__main__.py`), que pergunta antes de instalar ou baixar.
Toda funcao que toca o sistema recebe por parametro o que usa (`which`,
`run`, `popen`...), para os testes exercitarem cada caminho sem instalar
nada.

Os perfis de modelo foram conferidos no registro do Ollama em 2026-09-30
(tamanho do download = soma das camadas do manifesto), e escolhidos para
caber na memoria de video: um modelo que nao cabe roda com parte na RAM e
fica varias vezes mais lento.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlsplit

from .llm import ErroLLM, post_linhas_json

__all__ = [
    "ErroOllama",
    "Perfil",
    "PERFIS",
    "PlanoInstalacao",
    "normalizar_host",
    "hosts_candidatos",
    "versao",
    "localizar_servidor",
    "localizar_binario",
    "iniciar_servidor",
    "modelos_instalados",
    "tem_modelo",
    "tamanho_remoto",
    "baixar_modelo",
    "vram_gb",
    "perfil_para_vram",
    "resolver_modelo",
    "plano_de_instalacao",
    "executar_plano",
]

PORTA_PADRAO = 11434
URL_DOWNLOAD = "https://ollama.com/download"
URL_INSTALADOR_WINDOWS = "https://ollama.com/download/OllamaSetup.exe"
URL_SCRIPT_LINUX = "https://ollama.com/install.sh"
REGISTRO = "https://registry.ollama.ai/v2"


class ErroOllama(RuntimeError):
    """Instalacao, servidor ou download do modelo falhou."""


@dataclass(frozen=True)
class Perfil:
    nome: str
    modelo: str
    download_gb: float
    quando: str


PERFIS: dict[str, Perfil] = {p.nome: p for p in (
    Perfil("leve", "qwen2.5-coder:7b", 4.68, "GPU com menos de 10 GB, ou sem GPU NVIDIA"),
    Perfil("padrao", "qwen2.5-coder:14b", 8.99, "GPU de 10 a 23 GB"),
    Perfil("forte", "qwen3-coder:30b", 18.56, "GPU de 24 GB ou mais (MoE; roda com parte na RAM)"),
)}


# --------------------------------------------------------------------------
# servidor
# --------------------------------------------------------------------------

def normalizar_host(texto: str) -> str:
    """`OLLAMA_HOST` no formato do Ollama -> URL base (`http://host:porta`).

    `0.0.0.0` e o endereco em que o SERVIDOR escuta; como cliente, ele
    significa esta maquina.
    """
    t = texto.strip()
    if "://" not in t:
        t = "http://" + t
    partes = urlsplit(t)
    host = partes.hostname or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    if ":" in host:
        host = f"[{host}]"
    return f"{partes.scheme}://{host}:{partes.port or PORTA_PADRAO}"


def _gateway_wsl() -> str | None:
    """No WSL2, o IP do Windows visto de dentro da VM (nameserver do resolv)."""
    try:
        if "microsoft" not in Path("/proc/version").read_text().lower():
            return None
        for linha in Path("/etc/resolv.conf").read_text().splitlines():
            if linha.startswith("nameserver"):
                return linha.split()[1]
    except (OSError, IndexError):
        return None
    return None


def hosts_candidatos(ambiente: Mapping[str, str] | None = None) -> list[str]:
    """Onde procurar o servidor, em ordem: OLLAMA_HOST, esta maquina, o host
    do Docker e, no WSL2, o Windows."""
    amb = os.environ if ambiente is None else ambiente
    brutos = [amb["OLLAMA_HOST"]] if amb.get("OLLAMA_HOST") else []
    brutos += ["127.0.0.1", "host.docker.internal"]
    gateway = _gateway_wsl()
    if gateway:
        brutos.append(gateway)
    vistos: list[str] = []
    for b in brutos:
        url = normalizar_host(b)
        if url not in vistos:
            vistos.append(url)
    return vistos


def _get_json(url: str, *, timeout: float,
              headers: dict[str, str] | None = None) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.loads(r.read().decode("utf-8"))
            return dados if isinstance(dados, dict) else None
    except urllib.error.HTTPError as e:
        e.close()
        return None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def versao(base: str, timeout: float = 2.0) -> str | None:
    """A versao do servidor em `base`, ou None se ninguem responder ali."""
    dados = _get_json(f"{base}/api/version", timeout=timeout)
    return str(dados["version"]) if dados and dados.get("version") else None


def localizar_servidor(candidatos: list[str] | None = None,
                       timeout: float = 2.0) -> tuple[str, str] | None:
    """(base, versao) do primeiro candidato que responder."""
    for base in candidatos if candidatos is not None else hosts_candidatos():
        v = versao(base, timeout)
        if v:
            return base, v
    return None


def localizar_binario(which: Callable[[str], str | None] = shutil.which,
                      ambiente: Mapping[str, str] | None = None,
                      sistema: str | None = None) -> Path | None:
    """O executavel `ollama`: no PATH ou no lugar onde o instalador o poe.

    O instalador do Windows nao atualiza o PATH do terminal ja aberto, por
    isso o caminho padrao dele e procurado explicitamente.
    """
    achado = which("ollama")
    if achado:
        return Path(achado)
    amb = os.environ if ambiente is None else ambiente
    sistema = sistema or platform.system()
    candidatos: list[Path] = []
    if sistema == "Windows" and amb.get("LOCALAPPDATA"):
        candidatos.append(Path(amb["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe")
    elif sistema == "Darwin":
        candidatos.append(Path("/Applications/Ollama.app/Contents/Resources/ollama"))
    else:
        candidatos += [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]
    return next((c for c in candidatos if c.is_file()), None)


def iniciar_servidor(binario: Path, log: Path, *, base: str = "http://127.0.0.1:11434",
                     espera: float = 30.0,
                     popen: Callable[..., object] = subprocess.Popen,
                     sondar: Callable[[str], str | None] = versao,
                     dormir: Callable[[float], None] = time.sleep) -> str | None:
    """Sobe `ollama serve` desacoplado deste processo; devolve a versao.

    O servidor continua rodando depois que o gerador termina (e o que o
    app do Ollama tambem faz). A saida vai para `log`; se ele nao responder
    dentro de `espera` segundos, devolve None e o chamador aponta o log.
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    extra: dict = {}
    if sys.platform == "win32":
        # CREATE_NO_WINDOW, e nao DETACHED_PROCESS: um processo sem console
        # faz cada filho seu (o runner que carrega o modelo) abrir uma janela
        # de console nova, que pisca na tela; com um console oculto, os
        # filhos o herdam e nada aparece.
        extra["creationflags"] = (subprocess.CREATE_NO_WINDOW
                                  | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        extra["start_new_session"] = True
    with open(log, "ab") as saida:
        popen([str(binario), "serve"], stdout=saida, stderr=subprocess.STDOUT,
              stdin=subprocess.DEVNULL, **extra)
    limite = time.monotonic() + espera
    while True:
        v = sondar(base)
        if v:
            return v
        if time.monotonic() >= limite:
            return None
        dormir(0.5)


# --------------------------------------------------------------------------
# modelos
# --------------------------------------------------------------------------

def modelos_instalados(base: str, timeout: float = 10.0) -> list[str]:
    dados = _get_json(f"{base}/api/tags", timeout=timeout)
    if dados is None:
        raise ErroOllama(f"{base}/api/tags nao respondeu.")
    return [m.get("name") or m.get("model") for m in dados.get("models", [])
            if m.get("name") or m.get("model")]


def _completo(nome: str) -> str:
    """`qwen2.5-coder` e `qwen2.5-coder:latest` sao o mesmo modelo."""
    n = nome.strip().lower()
    return n if ":" in n.rsplit("/", 1)[-1] else n + ":latest"


def tem_modelo(instalados: list[str], nome: str) -> bool:
    alvo = _completo(nome)
    return any(_completo(m) == alvo for m in instalados)


def tamanho_remoto(nome: str, timeout: float = 10.0,
                   registro: str = REGISTRO) -> int | None:
    """Bytes a baixar, somando as camadas do manifesto no registro.

    Melhor esforco: sem rede, ou com um nome fora do registro oficial,
    devolve None e a pergunta de confirmacao diz "tamanho desconhecido".
    """
    repo, _, tag = _completo(nome).partition(":")
    if "/" not in repo:
        repo = f"library/{repo}"
    dados = _get_json(
        f"{registro}/{repo}/manifests/{tag}", timeout=timeout,
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})
    if not dados or not isinstance(dados.get("layers"), list):
        return None
    total = sum(int(c.get("size") or 0) for c in dados["layers"])
    return total or None


def baixar_modelo(base: str, nome: str,
                  ao_progredir: Callable[[str, int | None, int | None], None] | None = None,
                  timeout: float = 300.0) -> None:
    """`/api/pull` em streaming; `ao_progredir(status, baixado, total)`."""
    sucesso = False
    try:
        for ev in post_linhas_json(f"{base}/api/pull",
                                   {"model": nome, "stream": True}, timeout=timeout):
            if ev.get("error"):
                raise ErroOllama(f"download de {nome}: {ev['error']}")
            if ao_progredir:
                ao_progredir(str(ev.get("status", "")), ev.get("completed"), ev.get("total"))
            if ev.get("status") == "success":
                sucesso = True
    except ErroLLM as e:
        raise ErroOllama(f"download de {nome}: {e}") from None
    if not sucesso:
        raise ErroOllama(f"download de {nome} terminou sem confirmacao de sucesso.")


# --------------------------------------------------------------------------
# perfil pela memoria de video
# --------------------------------------------------------------------------

def vram_gb(run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
            which: Callable[[str], str | None] = shutil.which) -> float | None:
    """Memoria da maior GPU NVIDIA, em GiB, pelo `nvidia-smi`; None sem ela."""
    if not which("nvidia-smi"):
        return None
    try:
        r = run(["nvidia-smi", "--query-gpu=memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    valores = []
    for linha in (r.stdout or "").splitlines():
        try:
            valores.append(float(linha.strip()))
        except ValueError:
            continue
    return round(max(valores) / 1024, 1) if valores else None


def perfil_para_vram(vram: float | None) -> Perfil:
    if vram is None or vram < 10:
        return PERFIS["leve"]
    if vram < 24:
        return PERFIS["padrao"]
    return PERFIS["forte"]


def resolver_modelo(explicito: str | None, perfil: str | None,
                    configurado: str | None,
                    medir_vram: Callable[[], float | None] = vram_gb) -> tuple[str, str]:
    """(modelo, de onde veio a escolha) -- a origem sempre aparece na tela."""
    if explicito:
        return explicito, "--modelo"
    if perfil and perfil != "auto":
        if perfil not in PERFIS:
            raise ErroOllama(f"perfil {perfil!r} desconhecido; use "
                             f"auto, {', '.join(PERFIS)}")
        return PERFIS[perfil].modelo, f"perfil {perfil}"
    if configurado:
        return configurado, "RVGEN_MODELO"
    vram = medir_vram()
    p = perfil_para_vram(vram)
    medida = f"GPU de {vram} GB" if vram is not None else "sem GPU NVIDIA detectada"
    return p.modelo, f"perfil {p.nome} escolhido pela VRAM ({medida})"


# --------------------------------------------------------------------------
# instalacao
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanoInstalacao:
    """Como instalar o Ollama nesta plataforma.

    `baixar` = (url, nome do arquivo): baixado num diretorio temporario antes
    dos comandos; o marcador "{arquivo}" nos comandos vira o caminho dele.
    `manual` preenchido = nao ha como automatizar; so a instrucao.
    """

    descricao: str
    comandos: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    baixar: tuple[str, str] | None = None
    manual: str | None = None


def plano_de_instalacao(sistema: str | None = None,
                        which: Callable[[str], str | None] = shutil.which) -> PlanoInstalacao:
    sistema = sistema or platform.system()
    if sistema == "Windows":
        if which("winget"):
            return PlanoInstalacao(
                "winget install --id Ollama.Ollama -e  (pacote oficial, via winget)",
                comandos=(("winget", "install", "--id", "Ollama.Ollama", "-e"),))
        return PlanoInstalacao(
            f"baixar {URL_INSTALADOR_WINDOWS} e abrir o instalador",
            baixar=(URL_INSTALADOR_WINDOWS, "OllamaSetup.exe"),
            comandos=(("{arquivo}",),))
    if sistema == "Linux":
        return PlanoInstalacao(
            f"baixar o script oficial {URL_SCRIPT_LINUX} e rodar com sh (ele pede sudo)",
            baixar=(URL_SCRIPT_LINUX, "install.sh"),
            comandos=(("sh", "{arquivo}"),))
    if sistema == "Darwin" and which("brew"):
        return PlanoInstalacao("brew install ollama",
                               comandos=(("brew", "install", "ollama"),))
    return PlanoInstalacao("instalacao manual",
                           manual=f"baixe e instale a partir de {URL_DOWNLOAD}")


def _baixar_arquivo(url: str, destino: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(destino, "wb") as f:
            shutil.copyfileobj(r, f)
    except (urllib.error.URLError, OSError) as e:
        raise ErroOllama(f"nao foi possivel baixar {url}: {e}") from None


def executar_plano(plano: PlanoInstalacao,
                   run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                   baixar: Callable[[str, Path], None] = _baixar_arquivo) -> int:
    """Executa o plano no terminal do usuario (o instalador pode perguntar)."""
    if plano.manual:
        raise ErroOllama(plano.manual)
    with tempfile.TemporaryDirectory(prefix="rvgen_ollama_") as tmp:
        arquivo: Path | None = None
        if plano.baixar:
            url, nome = plano.baixar
            arquivo = Path(tmp) / nome
            baixar(url, arquivo)
        for cmd in plano.comandos:
            args = [str(arquivo) if a == "{arquivo}" else a for a in cmd]
            codigo = run(args).returncode
            if codigo != 0:
                return codigo
    return 0
