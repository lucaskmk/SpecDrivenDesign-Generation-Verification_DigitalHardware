#!/usr/bin/env python3
"""Testes do `rvgen preparar` e do modulo do Ollama -- sem instalar nada.

REQ: FR-RV-43 (cada item reportado), FR-RV-44 (instalar ou baixar so com
confirmacao), FR-RV-45 (iniciar o servidor com log), FR-RV-46 (perfil pela
VRAM).

O Ollama aqui e um servidor HTTP falso; instalador, `ollama serve` e
`nvidia-smi` sao funcoes falsas. O que interessa provar e o contrato: o que
e perguntado, o que NUNCA acontece sem um sim, e o que e reportado.
"""

from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from rvgen import __main__ as cli
from rvgen import ollama as ol
from rvgen.executor import Disponibilidade
from rvgen.tests.servidor_falso import ServidorFalso


class TestServidor(unittest.TestCase):

    def test_normalizar_host(self):
        self.assertEqual(ol.normalizar_host("127.0.0.1"), "http://127.0.0.1:11434")
        self.assertEqual(ol.normalizar_host("0.0.0.0:8080"), "http://127.0.0.1:8080")
        self.assertEqual(ol.normalizar_host("https://gpu.lab:443/"), "https://gpu.lab:443")
        self.assertEqual(ol.normalizar_host("host.docker.internal"),
                         "http://host.docker.internal:11434")

    def test_candidatos_comecam_pelo_OLLAMA_HOST_sem_repetir(self):
        c = ol.hosts_candidatos({"OLLAMA_HOST": "0.0.0.0"})
        self.assertEqual(c[0], "http://127.0.0.1:11434")
        self.assertEqual(len(c), len(set(c)))
        self.assertIn("http://host.docker.internal:11434", c)

    def test_localiza_o_primeiro_candidato_que_responde(self):
        rotas = {("GET", "/api/version"): lambda c, h: (200, {"version": "0.32.1"})}
        with ServidorFalso(rotas) as s:
            achado = ol.localizar_servidor(["http://127.0.0.1:9", s.url], timeout=1)
        self.assertEqual(achado, (s.url, "0.32.1"))
        self.assertIsNone(ol.localizar_servidor(["http://127.0.0.1:9"], timeout=1))

    def test_binario_no_lugar_do_instalador_windows(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "Programs" / "Ollama" / "ollama.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"")
            achado = ol.localizar_binario(which=lambda n: None,
                                          ambiente={"LOCALAPPDATA": d}, sistema="Windows")
        self.assertEqual(achado, exe)
        self.assertEqual(ol.localizar_binario(which=lambda n: "/opt/ollama"),
                         Path("/opt/ollama"))

    def test_iniciar_servidor_espera_responder_e_grava_log(self):
        chamados = []
        respostas = iter([None, None, "0.32.1"])
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "sub" / "serve.log"
            v = ol.iniciar_servidor(Path("ollama"), log,
                                    popen=lambda args, **kw: chamados.append(args),
                                    sondar=lambda base: next(respostas),
                                    dormir=lambda s: None)
            self.assertTrue(log.exists())
        self.assertEqual(v, "0.32.1")
        self.assertEqual(chamados, [["ollama", "serve"]])

    def test_iniciar_servidor_desiste_no_limite(self):
        with tempfile.TemporaryDirectory() as d:
            v = ol.iniciar_servidor(Path("ollama"), Path(d) / "s.log", espera=0,
                                    popen=lambda *a, **k: None,
                                    sondar=lambda base: None, dormir=lambda s: None)
        self.assertIsNone(v)


class TestModelos(unittest.TestCase):

    def test_latest_implicito(self):
        instalados = ["llama3.2:latest", "qwen2.5-coder:14b"]
        self.assertTrue(ol.tem_modelo(instalados, "llama3.2"))
        self.assertTrue(ol.tem_modelo(instalados, "QWEN2.5-coder:14b"))
        self.assertFalse(ol.tem_modelo(instalados, "qwen2.5-coder:7b"))

    def test_lista_e_download_com_progresso(self):
        pull = [{"status": "pulling manifest"},
                {"status": "pulling abc", "completed": 50, "total": 100},
                {"status": "pulling abc", "completed": 100, "total": 100},
                {"status": "success"}]
        rotas = {("GET", "/api/tags"): lambda c, h: (200, {"models": [{"name": "llama3.2:latest"}]}),
                 ("POST", "/api/pull"): lambda c, h: (200, pull)}
        vistos = []
        with ServidorFalso(rotas) as s:
            self.assertEqual(ol.modelos_instalados(s.url), ["llama3.2:latest"])
            ol.baixar_modelo(s.url, "qwen2.5-coder:14b",
                             lambda st, f, t: vistos.append((st, f, t)))
            self.assertEqual(s.recebidas[-1]["corpo"],
                             {"model": "qwen2.5-coder:14b", "stream": True})
        self.assertEqual(vistos[1], ("pulling abc", 50, 100))

    def test_download_com_erro_ou_sem_sucesso(self):
        for linhas, esperado in (([{"error": "pull model manifest: file does not exist"}],
                                  "file does not exist"),
                                 ([{"status": "pulling manifest"}], "sem confirmacao")):
            with ServidorFalso({("POST", "/api/pull"): lambda c, h, l=linhas: (200, l)}) as s:
                with self.assertRaisesRegex(ol.ErroOllama, esperado):
                    ol.baixar_modelo(s.url, "x")

    def test_tamanho_remoto_soma_as_camadas(self):
        manifesto = {"layers": [{"size": 8_988_000_000}, {"size": 1_000}]}
        rota = {("GET", "/v2/library/qwen2.5-coder/manifests/14b"):
                lambda c, h: (200, manifesto)}
        with ServidorFalso(rota) as s:
            self.assertEqual(ol.tamanho_remoto("qwen2.5-coder:14b", registro=f"{s.url}/v2"),
                             8_988_001_000)
            self.assertIsNone(ol.tamanho_remoto("inexistente", registro=f"{s.url}/v2"))


class TestPerfil(unittest.TestCase):

    def test_limiares(self):
        self.assertEqual(ol.perfil_para_vram(None).nome, "leve")
        self.assertEqual(ol.perfil_para_vram(8.0).nome, "leve")
        self.assertEqual(ol.perfil_para_vram(11.9).nome, "padrao")
        self.assertEqual(ol.perfil_para_vram(24.0).nome, "forte")

    def test_vram_pela_maior_gpu(self):
        run = lambda *a, **k: subprocess.CompletedProcess(a, 0, "12227\n8192\n", "")  # noqa: E731
        self.assertEqual(ol.vram_gb(run=run, which=lambda n: "nvidia-smi"), 11.9)
        self.assertIsNone(ol.vram_gb(which=lambda n: None))

    def test_resolver_diz_a_origem(self):
        self.assertEqual(ol.resolver_modelo("m:1", "forte", "cfg"), ("m:1", "--modelo"))
        self.assertEqual(ol.resolver_modelo(None, "forte", "cfg")[0], "qwen3-coder:30b")
        self.assertEqual(ol.resolver_modelo(None, None, "cfg"), ("cfg", "RVGEN_MODELO"))
        modelo, origem = ol.resolver_modelo(None, "auto", None, medir_vram=lambda: 11.9)
        self.assertEqual(modelo, "qwen2.5-coder:14b")
        self.assertIn("11.9", origem)


class TestInstalacao(unittest.TestCase):

    def test_plano_por_plataforma(self):
        win = ol.plano_de_instalacao("Windows", which=lambda n: "winget")
        self.assertEqual(win.comandos, (("winget", "install", "--id", "Ollama.Ollama", "-e"),))
        sem_winget = ol.plano_de_instalacao("Windows", which=lambda n: None)
        self.assertEqual(sem_winget.baixar, (ol.URL_INSTALADOR_WINDOWS, "OllamaSetup.exe"))
        linux = ol.plano_de_instalacao("Linux", which=lambda n: None)
        self.assertEqual(linux.baixar, (ol.URL_SCRIPT_LINUX, "install.sh"))
        self.assertEqual(linux.comandos, (("sh", "{arquivo}"),))
        self.assertIsNotNone(ol.plano_de_instalacao("Darwin", which=lambda n: None).manual)

    def test_executar_plano_baixa_e_substitui_o_arquivo(self):
        rodados, baixados = [], []

        def run(args, **kw):
            rodados.append(args)
            return subprocess.CompletedProcess(args, 0)

        plano = ol.plano_de_instalacao("Linux", which=lambda n: None)
        codigo = ol.executar_plano(plano, run=run,
                                   baixar=lambda url, dest: baixados.append((url, dest)))
        self.assertEqual(codigo, 0)
        self.assertEqual(baixados[0][0], ol.URL_SCRIPT_LINUX)
        self.assertEqual(rodados, [["sh", str(baixados[0][1])]])
        with self.assertRaises(ol.ErroOllama):
            ol.executar_plano(ol.PlanoInstalacao("manual", manual="baixe voce"))


class TestComandoPreparar(unittest.TestCase):
    """O que `preparar` faz -- e, principalmente, o que ele nao faz sem um sim."""

    def _rodar(self, argv, *, tty=False, servidor=None, binario=None,
               instalados=(), respostas=()):
        acoes = []
        entradas = iter(respostas)

        def valor_ou_sequencia(alvo, v):
            # lista = um valor por chamada, na ordem
            if isinstance(v, list):
                return mock.patch.object(ol, alvo, side_effect=v)
            return mock.patch.object(ol, alvo, return_value=v)

        patches = [
            valor_ou_sequencia("localizar_servidor", servidor),
            valor_ou_sequencia("localizar_binario", binario),
            mock.patch.object(ol, "modelos_instalados", return_value=list(instalados)),
            mock.patch.object(ol, "tamanho_remoto", return_value=8_990_000_000),
            mock.patch.object(ol, "vram_gb", return_value=11.9),
            mock.patch.object(ol, "executar_plano",
                              side_effect=lambda p: acoes.append("instalar") or 0),
            mock.patch.object(ol, "baixar_modelo",
                              side_effect=lambda *a, **k: acoes.append("baixar")),
            mock.patch.object(ol, "iniciar_servidor",
                              side_effect=lambda *a, **k: acoes.append("serve") or "0.32.1"),
            mock.patch.object(cli.ex, "checar_local",
                              return_value=Disponibilidade(False, "sem ghdl", "wsl")),
            mock.patch.object(cli.ex, "checar_docker",
                              return_value=Disponibilidade(True, "imagem ok")),
            mock.patch.object(cli, "_interativo", return_value=tty),
            mock.patch("builtins.input", side_effect=lambda *a: next(entradas)),
            mock.patch.dict("os.environ", {"RVGEN_MODELO": ""}, clear=False),
        ]
        for p in patches:
            p.start()
        try:
            saida = io.StringIO()
            with redirect_stdout(saida):
                codigo = cli.main(["preparar", "--sem-cor", *argv])
        finally:
            for p in reversed(patches):
                p.stop()
        return codigo, saida.getvalue(), acoes

    def test_verificar_nao_instala_nem_baixa_nem_inicia(self):
        codigo, saida, acoes = self._rodar(["--verificar"], tty=True)
        self.assertEqual(codigo, 1)
        self.assertEqual(acoes, [])
        self.assertIn("FALTA  Ollama nao esta instalado", saida)
        self.assertIn("so verificacao", saida)

    def test_sem_terminal_e_sem_sim_nao_age(self):
        codigo, saida, acoes = self._rodar([], tty=False, binario=None)
        self.assertEqual((codigo, acoes), (1, []))
        self.assertIn("sem terminal interativo", saida)

    def test_verificar_com_binario_mas_sem_servidor_so_aponta_o_comando(self):
        codigo, saida, acoes = self._rodar(["--verificar"], binario=Path("ollama.exe"))
        self.assertEqual((codigo, acoes), (1, []))
        self.assertIn('"ollama.exe" serve', saida)

    def test_resposta_nao_recusa_o_download(self):
        codigo, saida, acoes = self._rodar([], tty=True, servidor=("http://s", "0.32.1"),
                                           respostas=["n"])
        self.assertEqual((codigo, acoes), (1, []))
        self.assertIn("qwen2.5-coder:14b nao esta baixado", saida)
        self.assertIn("8.99 GB", saida)

    def test_sim_instala_inicia_e_baixa_e_termina_pronto(self):
        # sem servidor antes e logo depois da instalacao; o executavel so
        # aparece depois que o instalador roda
        codigo, saida, acoes = self._rodar(["--sim"], tty=False, servidor=[None, None],
                                           binario=[None, Path("ollama")])
        self.assertEqual(acoes, ["instalar", "serve", "baixar"])
        self.assertEqual(codigo, 0, saida)
        self.assertIn("executor do rvverify: docker", saida)
        self.assertIn("Tudo pronto", saida)

    def test_tudo_ja_pronto(self):
        codigo, saida, acoes = self._rodar(
            [], servidor=("http://127.0.0.1:11434", "0.32.1"), binario=Path("ollama"),
            instalados=["qwen2.5-coder:14b"])
        self.assertEqual((codigo, acoes), (0, []))
        self.assertIn("ok     modelo qwen2.5-coder:14b (perfil padrao", saida)


if __name__ == "__main__":
    unittest.main()
