#!/usr/bin/env python3
"""Logica do app de iteracoes de specs, sem HTTP (testavel direto).

Tres tipos de versao:

    base     iteracoes/base/specs   somente leitura; o app nunca escreve ali
    specs    specs/ da raiz         a "ativa": o que o rvgen le por padrao
    it-NNN   iteracoes/it-NNN/specs copia completa, editavel

Cada iteracao guarda os metadados em ``iteracoes/it-NNN/iteracao.json``.
Nada aqui roda o rvgen nem chama LLM: o app so mostra o comando.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from rvgen import contrato as ct

__all__ = [
    "ErroIteracoes",
    "ErroNaoEncontrado",
    "ErroPermissao",
    "Repositorio",
    "OBRIGATORIOS",
    "PAPEL_SISTEMA",
    "PAPEL_TESTES",
    "PAPEL_DOC",
    "papel_do_arquivo",
]

# Arquivos que o rvgen le (rvgen/contrato.py)
ARQUIVOS_SISTEMA = ("cpu.md", "vhdl.md", "riscv-rv32i.md")
ARQUIVO_TESTES = "testes.md"
OBRIGATORIOS = ARQUIVOS_SISTEMA + (ARQUIVO_TESTES,)

PAPEL_SISTEMA = "vai para a IA (prompt de sistema)"
PAPEL_TESTES = "vai para a IA (chamadas de teste)"
PAPEL_DOC = "so documentacao, a IA nao le"

_ID_ITERACAO_RE = re.compile(r"^it-\d{3}$")
# um trecho do caminho: letras (com acento), numeros, _ - . e espaco; nao
# comeca com ponto nem termina com ponto/espaco (o Windows os ignora)
_SEGMENTO_RE = re.compile(r"^[\w-](?:[\w.\- ]*[\w-])?$")
_EXPERIMENTO_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}$")
_PREFIXO_BACKUP = "antes-de-"
LIMITE_NOME = 120
LIMITE_NOTAS = 20_000
LIMITE_TEXTO = 1_000_000


class ErroIteracoes(ValueError):
    """Pedido invalido (id, caminho, nome...)."""


class ErroNaoEncontrado(ErroIteracoes):
    """Versao, arquivo ou experimento inexistente."""


class ErroPermissao(ErroIteracoes):
    """Escrita recusada (a base e somente leitura)."""


def papel_do_arquivo(rel: str) -> str:
    """Se o .md vai para a IA e em qual chamada."""
    if rel in ARQUIVOS_SISTEMA:
        return PAPEL_SISTEMA
    if rel == ARQUIVO_TESTES:
        return PAPEL_TESTES
    return PAPEL_DOC


def _rel_valido(rel: object) -> bool:
    """``rel`` e um .md relativo, com barras ``/`` e trechos simples."""
    if not isinstance(rel, str) or not rel.endswith(".md") or len(rel) > 255:
        return False
    return all(_SEGMENTO_RE.match(p) and ".." not in p for p in rel.split("/"))


def _tokens(chars: int) -> int:
    return round(chars / 4)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ler_texto(caminho: Path) -> str:
    """Le em UTF-8 e normaliza o fim de linha para ``\\n``."""
    return caminho.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


def _codificar(texto: str, oque: str = "texto") -> bytes:
    """UTF-8 estrito; recusa surrogates isolados (como um \\ud800 vindo do JSON)."""
    try:
        return texto.encode("utf-8")
    except UnicodeEncodeError as e:
        raise ErroIteracoes(f"{oque} com caractere inválido (posição {e.start}); "
                            "nada foi gravado") from e


def _gravar_atomico(caminho: Path, dados: bytes) -> None:
    """Grava num temporario da mesma pasta e troca de uma vez (os.replace).

    Se algo falhar no meio, o arquivo antigo fica intacto.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    existe = caminho.exists()
    if existe and not os.access(caminho, os.W_OK):
        raise PermissionError(f"{caminho.name} esta marcado como somente leitura")
    modo = (caminho.stat().st_mode & 0o777) if existe else 0o644
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, modo)
        os.replace(tmp, caminho)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _gravar_texto(caminho: Path, texto: str) -> None:
    """Grava mantendo o fim de linha que o arquivo ja usava (CRLF ou LF)."""
    texto = texto.replace("\r\n", "\n")
    crlf = caminho.exists() and b"\r\n" in caminho.read_bytes()
    if crlf:
        texto = texto.replace("\n", "\r\n")
    _gravar_atomico(caminho, _codificar(texto))  # codifica antes de tocar no arquivo


def _copiar_arvore(origem: Path, destino: Path) -> None:
    """Copia so o conteudo (sem o atributo somente leitura da base)."""
    shutil.copytree(origem, destino, copy_function=shutil.copyfile,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".*"))


class Repositorio:
    """As versoes das specs dentro de ``raiz`` (a raiz do repositorio)."""

    def __init__(self, raiz: Path | str) -> None:
        self.raiz = Path(raiz).resolve()
        self.pasta_iteracoes = self.raiz / "iteracoes"
        self.pasta_base = self.pasta_iteracoes / "base" / "specs"
        self.pasta_ativa = self.raiz / "specs"
        self.pasta_experimentos = self.raiz / "experimentos"

    # -- versoes ------------------------------------------------------------

    def validar_versao(self, versao: str) -> str:
        if not isinstance(versao, str) or not (
                versao in ("base", "specs") or _ID_ITERACAO_RE.match(versao)):
            raise ErroIteracoes(f"versão inválida: {versao!r} (use base, specs ou it-NNN)")
        return versao

    def pasta_da_versao(self, versao: str) -> Path:
        versao = self.validar_versao(versao)
        if versao == "base":
            pasta = self.pasta_base
        elif versao == "specs":
            pasta = self.pasta_ativa
        else:
            pasta = self.pasta_iteracoes / versao / "specs"
        if not pasta.is_dir():
            raise ErroNaoEncontrado(f"versão {versao} não existe ({self._rel(pasta)})")
        return pasta

    def caminho_relativo_da_versao(self, versao: str) -> str:
        """Pasta da versao relativa a raiz, com barras POSIX (vai no comando)."""
        return self._rel(self.pasta_da_versao(versao))

    def _rel(self, caminho: Path) -> str:
        try:
            return caminho.resolve().relative_to(self.raiz).as_posix()
        except ValueError:
            return str(caminho)

    def _ids_iteracoes(self) -> list[str]:
        if not self.pasta_iteracoes.is_dir():
            return []
        return sorted(p.name for p in self.pasta_iteracoes.iterdir()
                      if p.is_dir() and _ID_ITERACAO_RE.match(p.name)
                      and (p / "specs").is_dir())

    def _arquivo_meta(self, it: str) -> Path:
        return self.pasta_iteracoes / it / "iteracao.json"

    def ler_meta(self, it: str) -> dict:
        if not _ID_ITERACAO_RE.match(self.validar_versao(it)):
            raise ErroIteracoes(f"{it} não é uma iteração (it-NNN)")
        self.pasta_da_versao(it)
        meta = {"id": it, "nome": it, "criada_em": None, "origem": None,
                "notas": "", "experimentos": []}
        try:
            dados = json.loads(self._arquivo_meta(it).read_text(encoding="utf-8"))
            if isinstance(dados, dict):
                meta.update({k: v for k, v in dados.items() if k in meta})
        except (OSError, json.JSONDecodeError):
            pass
        meta["id"] = it
        if not isinstance(meta["experimentos"], list):
            meta["experimentos"] = []
        return meta

    def _gravar_meta(self, meta: dict) -> None:
        texto = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
        _gravar_atomico(self._arquivo_meta(meta["id"]), _codificar(texto, "metadados"))

    def _conteudo(self, versao: str) -> dict[str, bytes]:
        """{rel: bytes} de todos os .md da versao (para comparar copias)."""
        pasta = self.pasta_da_versao(versao)
        return {rel: (pasta / rel).read_bytes().replace(b"\r\n", b"\n")
                for rel in self._rels(pasta)}

    def listar(self) -> dict:
        """Base, ativa e cada iteracao, com metadados."""
        ativa = self._conteudo("specs") if self.pasta_ativa.is_dir() else None
        versoes = [
            {"id": "base", "nome": "Base", "origem": None, "somente_leitura": True,
             "pasta": self._rel(self.pasta_base), "existe": self.pasta_base.is_dir()},
            {"id": "specs", "nome": "Ativa (specs/)", "origem": None,
             "somente_leitura": False, "pasta": self._rel(self.pasta_ativa),
             "existe": self.pasta_ativa.is_dir()},
        ]
        for it in self._ids_iteracoes():
            meta = self.ler_meta(it)
            meta.update({"somente_leitura": False, "existe": True,
                         "pasta": self._rel(self.pasta_iteracoes / it / "specs"),
                         "igual_a_ativa": ativa is not None and self._conteudo(it) == ativa})
            versoes.append(meta)
        return {"versoes": versoes}

    # -- criar e editar iteracoes --------------------------------------------

    def _proximo_id(self) -> str:
        ids = [int(i[3:]) for i in self._ids_iteracoes()]
        if self.pasta_iteracoes.is_dir():  # pastas sem specs/ tambem ocupam o numero
            ids += [int(p.name[3:]) for p in self.pasta_iteracoes.iterdir()
                    if _ID_ITERACAO_RE.match(p.name)]
        n = max(ids, default=0) + 1
        if n > 999:
            raise ErroIteracoes("limite de 999 iterações atingido")
        return f"it-{n:03d}"

    @staticmethod
    def _limpar_nome(nome: object, padrao: str) -> str:
        nome = str(nome or "").strip()
        nome = re.sub(r"[\x00-\x1f]", " ", nome)
        if len(nome) > LIMITE_NOME:
            raise ErroIteracoes(f"nome longo demais (máx. {LIMITE_NOME} caracteres)")
        _codificar(nome, "nome")
        return nome or padrao

    @staticmethod
    def _limpar_notas(notas: object) -> str:
        notas = str(notas or "")
        if len(notas) > LIMITE_NOTAS:
            raise ErroIteracoes(f"notas longas demais (máx. {LIMITE_NOTAS} caracteres)")
        _codificar(notas, "notas")
        return notas

    def criar_iteracao(self, origem: str = "base", nome: str = "", notas: str = "") -> str:
        """Copia a versao ``origem`` para um novo it-NNN e devolve o id."""
        origem = self.validar_versao(origem)
        pasta_origem = self.pasta_da_versao(origem)
        nome = self._limpar_nome(nome, f"cópia de {origem}")
        notas = self._limpar_notas(notas)
        self.pasta_iteracoes.mkdir(parents=True, exist_ok=True)
        for _ in range(5):                         # outra aba pode criar ao mesmo tempo
            it = self._proximo_id()
            pasta = self.pasta_iteracoes / it
            try:
                pasta.mkdir()
                break
            except FileExistsError:
                continue
        else:
            raise ErroIteracoes("não foi possível reservar um id de iteração")
        try:
            _copiar_arvore(pasta_origem, pasta / "specs")
            self._gravar_meta({"id": it, "nome": nome, "criada_em": _agora(),
                               "origem": origem, "notas": notas, "experimentos": []})
        except BaseException:
            shutil.rmtree(pasta, ignore_errors=True)
            raise
        return it

    def atualizar_iteracao(self, it: str, nome: str | None = None,
                           notas: str | None = None) -> dict:
        meta = self.ler_meta(it)
        if nome is not None:
            meta["nome"] = self._limpar_nome(nome, it)
        if notas is not None:
            meta["notas"] = self._limpar_notas(notas)
        self._gravar_meta(meta)
        return meta

    # -- arquivos -----------------------------------------------------------

    @staticmethod
    def _rels(pasta: Path) -> list[str]:
        """Os .md da pasta (recursivo) cujo nome o app aceita."""
        return sorted(rel for rel in (p.relative_to(pasta).as_posix()
                                      for p in pasta.rglob("*.md") if p.is_file())
                      if _rel_valido(rel))

    def validar_rel(self, versao: str, rel: str, *, existir: bool = True) -> Path:
        """Caminho absoluto de ``rel`` dentro da pasta da versao, ou erro.

        So aceita .md com nome simples (sem ``..``, sem absoluto, sem ``\\``)
        e confirma, depois de resolver, que o arquivo fica dentro da pasta.
        """
        if not _rel_valido(rel):
            raise ErroIteracoes(f"arquivo inválido: {rel!r} (só .md dentro da pasta de specs)")
        partes = PurePosixPath(rel).parts
        pasta = self.pasta_da_versao(versao).resolve()
        caminho = (pasta / Path(*partes)).resolve()
        if caminho == pasta or pasta not in caminho.parents:
            raise ErroIteracoes(f"arquivo fora da pasta de specs: {rel!r}")
        if existir and not caminho.is_file():
            raise ErroNaoEncontrado(f"{rel} não existe em {versao}")
        return caminho

    def arquivos(self, versao: str) -> list[dict]:
        """Os .md da versao com papel e tamanho."""
        pasta = self.pasta_da_versao(versao)
        saida = []
        for rel in self._rels(pasta):
            chars = len(_ler_texto(pasta / rel))
            saida.append({"rel": rel, "papel": papel_do_arquivo(rel),
                          "chars": chars, "tokens": _tokens(chars)})
        return saida

    def obrigatorios_ausentes(self, versao: str) -> list[str]:
        """Os arquivos que o rvgen le e que faltam nesta versao."""
        pasta = self.pasta_da_versao(versao)
        return [rel for rel in OBRIGATORIOS if not (pasta / rel).is_file()]

    def ler_arquivo(self, versao: str, rel: str) -> str:
        return _ler_texto(self.validar_rel(versao, rel))

    def salvar_arquivo(self, versao: str, rel: str, texto: str) -> dict:
        """Grava um .md. Recusa a base; na ativa, faz backup antes.

        Devolve ``{"alterado": bool, "backup": id ou None}``.
        """
        versao = self.validar_versao(versao)
        if versao == "base":
            raise ErroPermissao("a base é somente leitura; crie uma iteração a partir dela")
        if not isinstance(texto, str):
            raise ErroIteracoes("texto inválido")
        if len(texto) > LIMITE_TEXTO:
            raise ErroIteracoes(f"texto longo demais (máx. {LIMITE_TEXTO} caracteres)")
        _codificar(texto)                          # antes do backup e da gravacao
        caminho = self.validar_rel(versao, rel, existir=False)
        # so edita o que existe; criar, so um obrigatorio que sumiu
        if not caminho.is_file() and rel not in OBRIGATORIOS:
            raise ErroIteracoes(f"{rel} não existe em {versao}; o app só edita arquivos "
                                f"existentes (ou recria {', '.join(OBRIGATORIOS)})")
        texto = texto.replace("\r\n", "\n")
        if caminho.is_file() and _ler_texto(caminho) == texto:
            return {"alterado": False, "backup": None}
        backup = self._backup_da_ativa() if versao == "specs" else None
        try:
            _gravar_texto(caminho, texto)
        except PermissionError as e:
            raise ErroPermissao(f"sem permissão para gravar {rel}: {e}") from e
        return {"alterado": True, "backup": backup}

    def _backup_da_ativa(self) -> str:
        """Garante uma iteracao automatica igual a ativa; devolve o id dela."""
        atual = self._conteudo("specs")
        for it in reversed(self._ids_iteracoes()):
            meta = self.ler_meta(it)
            if str(meta.get("nome", "")).startswith(_PREFIXO_BACKUP) and self._conteudo(it) == atual:
                return it
        return self.criar_iteracao(
            "specs", "antes-de-editar-specs",
            "Backup automático: cópia de specs/ feita antes de editar a ativa pelo app.")

    # -- comparar -----------------------------------------------------------

    def diff(self, versao_a: str, versao_b: str, rel: str) -> dict:
        """Diff unificado de um .md entre duas versoes."""
        textos = []
        for versao in (versao_a, versao_b):
            caminho = self.validar_rel(versao, rel, existir=False)
            textos.append(_ler_texto(caminho) if caminho.is_file() else None)
        a, b = textos
        if a is None and b is None:
            raise ErroNaoEncontrado(f"{rel} não existe em {versao_a} nem em {versao_b}")
        linhas = list(difflib.unified_diff(
            (a or "").splitlines(), (b or "").splitlines(),
            fromfile=f"{versao_a}/{rel}", tofile=f"{versao_b}/{rel}", lineterm=""))
        mais = sum(1 for ln in linhas if ln.startswith("+") and not ln.startswith("+++"))
        menos = sum(1 for ln in linhas if ln.startswith("-") and not ln.startswith("---"))
        return {"rel": rel, "a": versao_a, "b": versao_b, "existe_a": a is not None,
                "existe_b": b is not None, "igual": a == b, "mais": mais, "menos": menos,
                "texto": "\n".join(linhas)}

    def resumo_diferencas(self, versao_a: str, versao_b: str) -> dict:
        """Quais .md mudaram de A para B e quantas linhas."""
        pasta_a, pasta_b = self.pasta_da_versao(versao_a), self.pasta_da_versao(versao_b)
        rels = sorted(set(self._rels(pasta_a)) | set(self._rels(pasta_b)))
        arquivos = []
        for rel in rels:
            d = self.diff(versao_a, versao_b, rel)
            if not d["existe_a"]:
                estado = "so em B"
            elif not d["existe_b"]:
                estado = "so em A"
            else:
                estado = "igual" if d["igual"] else "alterado"
            arquivos.append({"rel": rel, "estado": estado, "mais": d["mais"],
                             "menos": d["menos"], "papel": papel_do_arquivo(rel)})
        mudados = [a for a in arquivos if a["estado"] != "igual"]
        return {"a": versao_a, "b": versao_b, "arquivos": arquivos,
                "mudados": len(mudados),
                "mais": sum(a["mais"] for a in arquivos),
                "menos": sum(a["menos"] for a in arquivos)}

    # -- analise ------------------------------------------------------------

    def prompt(self, versao: str) -> dict:
        """O prompt que a IA recebe com as specs desta versao.

        Mesma montagem do rvgen/agente.py: ``texto_do_contrato`` para o
        prompt de sistema e contrato + testes.md para as chamadas de teste.
        """
        pasta = self.pasta_da_versao(versao)
        aviso = None
        try:
            cpu = ct.ler_configuracao_cpu(pasta / "cpu.md")
        except ct.ErroContrato:
            # o rvgen pararia aqui; monta mesmo assim para mostrar o texto
            cpu = {"microarquitetura": "monociclo", "isa": "rv32i"}
            aviso = ("cpu.md não declara ISA/microarquitetura válidas: o rvgen recusaria "
                     "estas specs. O texto abaixo foi montado com monociclo/rv32i só "
                     "para visualização.")
        try:
            sistema = ct.texto_do_contrato(cpu["microarquitetura"], cpu["isa"], pasta)
        except ct.ErroContrato as e:
            return {"versao": versao, "ok": False, "erro": self._sem_raiz(str(e)),
                    "aviso": aviso, "microarquitetura": cpu["microarquitetura"],
                    "isa": cpu["isa"], "sistema": None, "testes": None}
        try:
            testes = sistema + "\n\n# Cocotb Testbench Rules\n" + ct.texto_de_testes(pasta)
        except ct.ErroContrato as e:
            testes = None
            aviso = (aviso + " " if aviso else "") + self._sem_raiz(str(e))
        return {"versao": versao, "ok": True, "erro": None, "aviso": aviso,
                "microarquitetura": cpu["microarquitetura"], "isa": cpu["isa"],
                "sistema": sistema, "testes": testes}

    def _sem_raiz(self, texto: str) -> str:
        """Tira o caminho absoluto da raiz das mensagens."""
        for raiz in {str(self.raiz), self.raiz.as_posix()}:
            texto = texto.replace(raiz + "\\", "").replace(raiz + "/", "")
        return texto

    @staticmethod
    def _tamanho_prompt(p: dict) -> dict:
        def medir(texto):
            if texto is None:
                return None
            return {"chars": len(texto), "tokens": _tokens(len(texto))}
        return {"sistema": medir(p["sistema"]), "testes": medir(p["testes"])}

    def analisar(self, versao: str) -> dict:
        """Analise deterministica (sem LLM) das specs de uma versao."""
        pasta = self.pasta_da_versao(versao)
        arquivos = self.arquivos(versao)
        checagens: list[dict] = []

        def checar(nivel: str, arquivo: str | None, mensagem: str) -> None:
            checagens.append({"nivel": nivel, "arquivo": arquivo, "mensagem": mensagem})

        textos = {a["rel"]: _ler_texto(pasta / a["rel"]) for a in arquivos}
        for rel in OBRIGATORIOS:
            if rel not in textos:
                checar("erro", rel, f"{rel} ausente: o rvgen precisa dele para montar o prompt.")
            elif not textos[rel].strip():
                checar("erro", rel, f"{rel} está vazio: o rvgen precisa dele para montar o prompt.")

        cpu_md = textos.get("cpu.md")
        if cpu_md is not None:
            try:
                ct.ler_configuracao_cpu(pasta / "cpu.md")
            except ct.ErroContrato as e:
                motivo = str(e).replace(str(pasta / "cpu.md"), "cpu.md").removeprefix("cpu.md: ")
                checar("erro", "cpu.md", f"ISA/microarquitetura: {self._sem_raiz(motivo)}. "
                       "O rvgen recusa gerar com este cpu.md.")
            self._checar_entidade(cpu_md, checar)

        ia = [rel for rel in OBRIGATORIOS if rel in textos]
        for rel in ia:
            texto = textos[rel]
            req = texto.count("-- REQ:")
            fr = len(re.findall(r"FR-RV-", texto))
            if req or fr:
                partes = []
                if req:
                    partes.append(f"{req}x \"-- REQ:\"")
                if fr:
                    partes.append(f"{fr}x \"FR-RV-\"")
                checar("aviso", rel, f"{' e '.join(partes)} em um arquivo que vai para a IA: "
                       "são IDs de requisito sem definição nas specs; o modelo pode copiá-los "
                       "ou tentar segui-los.")
            if re.search(r"\brvverify\b", texto, re.IGNORECASE):
                checar("info", rel, "cita o rvverify: confira se o texto não o trata como "
                       "autoridade. O juiz do rvgen é o spec-riscv-test; o rvverify valida "
                       "entregas por cpu.toml.")

        p = self.prompt(versao)
        if p["aviso"] and p["ok"]:
            checar("info", None, p["aviso"])
        tamanho = self._tamanho_prompt(p)
        variacao = None
        if versao != "base" and self.pasta_base.is_dir():
            base = self._tamanho_prompt(self.prompt("base"))
            variacao = {}
            for chave in ("sistema", "testes"):
                atual, ref = tamanho[chave], base[chave]
                if atual and ref and ref["chars"]:
                    variacao[chave] = round(100.0 * (atual["chars"] - ref["chars"]) / ref["chars"], 1)
                else:
                    variacao[chave] = None
            variacao["base"] = base
        ordem = {"erro": 0, "aviso": 1, "info": 2}
        checagens.sort(key=lambda c: ordem.get(c["nivel"], 3))
        return {
            "versao": versao,
            "arquivos": arquivos,
            "checagens": checagens,
            "contagem": {n: sum(1 for c in checagens if c["nivel"] == n)
                         for n in ("erro", "aviso", "info")},
            "prompt": {"ok": p["ok"], "erro": p["erro"], "isa": p["isa"],
                       "microarquitetura": p["microarquitetura"], **tamanho},
            "variacao_vs_base": variacao,
        }

    @staticmethod
    def _checar_entidade(cpu_md: str, checar) -> None:
        bloco = re.search(r"\bentity\s+cpu\s+is\b(.*?)\bend\s+(?:entity\s+)?(?:cpu\s*)?;",
                          cpu_md, re.IGNORECASE | re.DOTALL)
        if not bloco:
            checar("erro", "cpu.md", "bloco \"entity cpu is ... end cpu;\" ausente: o "
                   "contrato da interface externa precisa estar no cpu.md.")
            return
        corpo = "\n".join(ln.split("--", 1)[0] for ln in bloco.group(1).splitlines())
        if re.search(r"\bgeneric\b", corpo, re.IGNORECASE):
            checar("erro", "cpu.md", "a entidade cpu declara \"generic\": o spec-riscv-test "
                   "recusa uma entidade com generic.")
        faltando = [p for p in ct._PORTAS_CPU
                    if not re.search(rf"\b{p}\s*:", corpo, re.IGNORECASE)]
        for porta in faltando:
            checar("erro", "cpu.md", f"a entidade cpu não declara a porta \"{porta}\" "
                   f"(são {len(ct._PORTAS_CPU)} portas obrigatórias).")

    # -- promover -----------------------------------------------------------

    def promover(self, it: str) -> dict:
        """Copia a iteracao para specs/; antes, guarda a ativa numa iteracao.

        Devolve ``{"backup": id do backup, "copiados": [...], "mantidos": [...]}``.
        Arquivos que so existem na ativa sao mantidos (estao no backup).
        """
        if not _ID_ITERACAO_RE.match(self.validar_versao(it)):
            raise ErroIteracoes("só uma iteração (it-NNN) pode ser promovida")
        origem = self.pasta_da_versao(it)
        self.pasta_ativa.mkdir(parents=True, exist_ok=True)
        backup = self.criar_iteracao(
            "specs", f"antes-de-promover-{it}",
            f"Backup automático: specs/ como estava antes de promover {it}.")
        copiados = []
        for arq in sorted(origem.rglob("*")):
            if not arq.is_file() or any(p.startswith(".") or p == "__pycache__"
                                        for p in arq.relative_to(origem).parts):
                continue
            rel = arq.relative_to(origem).as_posix()
            destino = self.pasta_ativa / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.is_file() and destino.read_bytes() == arq.read_bytes():
                continue
            if rel.endswith(".md"):
                _gravar_texto(destino, _ler_texto(arq))
            else:
                shutil.copyfile(arq, destino)
            copiados.append(rel)
        mantidos = sorted(set(self._rels(self.pasta_ativa)) - set(self._rels(origem)))
        return {"backup": backup, "copiados": copiados, "mantidos": mantidos}

    # -- experimentos -------------------------------------------------------

    @staticmethod
    def validar_experimento(nome: str) -> str:
        nome = str(nome or "").strip()
        if not _EXPERIMENTO_RE.match(nome) or ".." in nome:
            raise ErroIteracoes(f"nome de experimento inválido: {nome!r} "
                                "(letras, números, _ . -; é a pasta em experimentos/)")
        return nome

    def vincular_experimento(self, it: str, nome: str) -> dict:
        nome = self.validar_experimento(nome)
        meta = self.ler_meta(it)
        if nome not in meta["experimentos"]:
            meta["experimentos"].append(nome)
            self._gravar_meta(meta)
        return meta

    def desvincular_experimento(self, it: str, nome: str) -> dict:
        nome = self.validar_experimento(nome)
        meta = self.ler_meta(it)
        if nome in meta["experimentos"]:
            meta["experimentos"].remove(nome)
            self._gravar_meta(meta)
        return meta

    def resultado_experimento(self, nome: str) -> dict:
        """Resultado da sessao mais recente de ``experimentos/<nome>``."""
        nome = self.validar_experimento(nome)
        pasta = self.pasta_experimentos / nome
        saida = {"nome": nome, "pasta": f"experimentos/{nome}", "existe": pasta.is_dir(),
                 "sessao": None, "resultado": None, "specs": None, "sessoes": 0}
        if not pasta.is_dir():
            return saida
        sessoes = sorted((p for p in (pasta / ".rvgen").glob("sessao-*")
                          if (p / "resultado.json").is_file()), key=lambda p: p.name)
        saida["sessoes"] = len(sessoes)
        if not sessoes:
            return saida
        sessao = sessoes[-1]
        saida["sessao"] = sessao.name
        try:
            dados = json.loads((sessao / "resultado.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            saida["erro"] = f"resultado.json ilegível: {e}"
            return saida
        if isinstance(dados, dict):
            chaves = ("veredito", "objetivo_atingido", "placar", "chamadas", "iteracoes",
                      "tokens_entrada", "tokens_saida", "segundos", "provedor", "modelo",
                      "isa", "microarquitetura")
            saida["resultado"] = {k: dados.get(k) for k in chaves if k in dados}
        try:
            with open(sessao / "sessao.jsonl", encoding="utf-8") as f:
                for linha in f:
                    ev = json.loads(linha)
                    if ev.get("evento") == "inicio":
                        saida["specs"] = ev.get("specs")
                        break
        except (OSError, json.JSONDecodeError):
            pass
        return saida
