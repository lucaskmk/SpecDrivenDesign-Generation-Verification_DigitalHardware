#!/usr/bin/env python3
"""Testes do cliente unico de LLM, contra servidores HTTP falsos.

REQ: FR-RV-46 (Ollama e OpenRouter pela mesma interface), FR-RV-50 (tokens
e duracao de cada chamada).

Nada aqui fala com um modelo de verdade: o que se testa e o CONTRATO de cada
API -- o que o cliente manda, como junta o streaming, como relata o erro que
o servidor deu. unittest da biblioteca padrao, para rodar num host sem
pytest; o pytest do repositorio coleta estes testes igual.
"""

from __future__ import annotations

import unittest

from rvgen.config import carregar_env, ler_config
from rvgen.llm import (ClienteGemini, ClienteOllama, ClienteOpenAI, ErroLLM, extrair_json,
                       extrair_python, extrair_vhdl)
from rvgen.tests.servidor_falso import ServidorFalso


class TestClienteOllama(unittest.TestCase):

    def test_junta_o_streaming_e_conta_tokens(self):
        pedacos = [
            {"message": {"role": "assistant", "content": "entity "}, "done": False},
            {"message": {"role": "assistant", "content": "alu is"}, "done": False},
            {"message": {"role": "assistant", "content": ""}, "done": True,
             "prompt_eval_count": 120, "eval_count": 7},
        ]
        progresso: list[int] = []
        with ServidorFalso({("POST", "/api/chat"): lambda c, h: (200, pedacos)}) as s:
            cliente = ClienteOllama(s.url, "qwen2.5-coder:14b", num_ctx=8192,
                                    ao_progredir=progresso.append)
            r = cliente.conversar([{"role": "user", "content": "oi"}])
            enviado = s.recebidas[0]["corpo"]
        self.assertEqual(r.texto, "entity alu is")
        self.assertEqual((r.tokens_entrada, r.tokens_saida), (120, 7))
        self.assertEqual((r.provedor, r.modelo), ("ollama", "qwen2.5-coder:14b"))
        self.assertEqual(progresso, [7, 13])
        # a API nativa e usada justamente por aceitar num_ctx
        self.assertEqual(enviado["options"]["num_ctx"], 8192)
        self.assertTrue(enviado["stream"])
        self.assertNotIn("format", enviado)

    def test_schema_vai_no_campo_format(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        fim = [{"message": {"content": '{"x": 1}'}, "done": True}]
        with ServidorFalso({("POST", "/api/chat"): lambda c, h: (200, fim)}) as s:
            r = ClienteOllama(s.url, "m").conversar([], schema=schema)
            self.assertEqual(s.recebidas[0]["corpo"]["format"], schema)
        self.assertEqual(extrair_json(r.texto), {"x": 1})

    def test_erro_no_meio_do_streaming_vira_ErroLLM(self):
        linhas = [{"error": "model 'x' not found, try pulling it first"}]
        with ServidorFalso({("POST", "/api/chat"): lambda c, h: (200, linhas)}) as s:
            with self.assertRaisesRegex(ErroLLM, "try pulling it first"):
                ClienteOllama(s.url, "x").conversar([])

    def test_erro_http_traz_a_mensagem_do_servidor(self):
        rota = lambda c, h: (404, {"error": "model \"x\" not found"})  # noqa: E731
        with ServidorFalso({("POST", "/api/chat"): rota}) as s:
            with self.assertRaisesRegex(ErroLLM, r"HTTP 404: model \"x\" not found"):
                ClienteOllama(s.url, "x").conversar([])

    def test_corte_do_servidor_e_retomado_com_o_texto_parcial(self):
        # o que o Ollama 0.32.1 fez de verdade na TRV-9.8: encerrou o streaming
        # no meio de um literal "000...0", sem `done` e sem erro
        def rota(corpo, h):
            ultima = corpo["messages"][-1]
            if ultima["role"] != "assistant":                  # 1o pedido: cortado
                return 200, [{"message": {"content": 'r <= "000'}, "done": False},
                             {"message": {"content": "0"}, "done": False}]
            self.assertEqual(ultima["content"], 'r <= "0000')  # retoma do ponto exato
            return 200, [{"message": {"content": '0";'}, "done": False},
                         {"message": {"content": ""}, "done": True,
                          "prompt_eval_count": 9, "eval_count": 3}]

        progresso: list[int] = []
        with ServidorFalso({("POST", "/api/chat"): rota}) as s:
            r = ClienteOllama(s.url, "m", ao_progredir=progresso.append).conversar(
                [{"role": "system", "content": "c"}, {"role": "user", "content": "u"}])
            pedidos = [q["corpo"]["messages"] for q in s.recebidas]
        self.assertEqual(r.texto, 'r <= "00000";')
        self.assertEqual(r.cortes, 1)
        self.assertEqual(r.tokens_saida, 3 + 2)       # 2 linhas do trecho cortado
        self.assertEqual(len(pedidos), 2)
        self.assertEqual(len(pedidos[0]), 2)          # o pedido original nao muda
        self.assertEqual(progresso[-1], len(r.texto))

    def test_corte_sem_texto_novo_ou_repetido_demais_vira_erro(self):
        vazio = [{"message": {"content": ""}, "done": False}]
        with ServidorFalso({("POST", "/api/chat"): lambda c, h: (200, vazio)}) as s:
            with self.assertRaisesRegex(ErroLLM, "sem texto novo"):
                ClienteOllama(s.url, "m").conversar([{"role": "user", "content": "u"}])
        sempre = [{"message": {"content": "0"}, "done": False}]
        with ServidorFalso({("POST", "/api/chat"): lambda c, h: (200, sempre)}) as s:
            with self.assertRaisesRegex(ErroLLM, "cortada pelo servidor 3 vezes"):
                ClienteOllama(s.url, "m", max_cortes=2).conversar(
                    [{"role": "user", "content": "u"}])
            self.assertEqual(len(s.recebidas), 3)

    def test_temperatura_por_chamada_chega_a_api_nos_dois_provedores(self):
        fim = [{"message": {"content": "x"}, "done": True}]
        resposta = {"choices": [{"message": {"content": "x"}}]}
        with ServidorFalso({("POST", "/api/chat"): lambda c, h: (200, fim),
                            ("POST", "/v1/chat/completions"): lambda c, h: (200, resposta)}) as s:
            ClienteOllama(s.url, "m", temperatura=0.2).conversar([], temperatura=0.9)
            ClienteOllama(s.url, "m", temperatura=0.2).conversar([])
            ClienteOpenAI(f"{s.url}/v1", "sk", "m", temperatura=0.2).conversar([], temperatura=0.6)
            enviados = [q["corpo"] for q in s.recebidas]
        self.assertEqual(enviados[0]["options"]["temperature"], 0.9)
        self.assertEqual(enviados[1]["options"]["temperature"], 0.2)
        self.assertEqual(enviados[2]["temperature"], 0.6)

    def test_sem_servidor_diz_que_nao_conectou(self):
        with self.assertRaisesRegex(ErroLLM, "sem conexao"):
            ClienteOllama("http://127.0.0.1:9", "x", timeout=2).conversar([])


class TestClienteOpenAI(unittest.TestCase):

    def test_manda_a_chave_e_le_choices_e_usage(self):
        resposta = {"model": "openai/gpt-5.6-luna",
                    "choices": [{"message": {"role": "assistant", "content": "ok"},
                                 "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 2}}
        with ServidorFalso({("POST", "/api/v1/chat/completions"):
                            lambda c, h: (200, resposta)}) as s:
            cliente = ClienteOpenAI(f"{s.url}/api/v1", "sk-teste", "openai/gpt-5.6-luna")
            r = cliente.conversar([{"role": "user", "content": "oi"}],
                                  schema={"type": "object"})
            req = s.recebidas[0]
        self.assertEqual(r.texto, "ok")
        self.assertEqual((r.tokens_entrada, r.tokens_saida), (50, 2))
        self.assertEqual(r.motivo_finalizacao, "length")
        self.assertEqual(r.provedor, "openrouter")
        self.assertEqual(req["cabecalhos"]["authorization"], "Bearer sk-teste")
        # o schema nao vai para a API externa (ver a docstring de rvgen.llm)
        self.assertNotIn("response_format", req["corpo"])

    def test_sem_chave_recusa_antes_de_chamar(self):
        with self.assertRaisesRegex(ErroLLM, "OPENROUTER_API_KEY"):
            ClienteOpenAI("http://127.0.0.1:9", None, "m").conversar([])

    def test_erro_http_traz_a_mensagem_do_provedor(self):
        rota = lambda c, h: (401, {"error": {"message": "No auth credentials found"}})  # noqa: E731
        with ServidorFalso({("POST", "/v1/chat/completions"): rota}) as s:
            with self.assertRaisesRegex(ErroLLM, "HTTP 401: No auth credentials found"):
                ClienteOpenAI(f"{s.url}/v1", "sk-x", "m").conversar([])


class TestClienteGemini(unittest.TestCase):

    def test_mapeia_mensagens_schema_e_usage(self):
        resposta = {"candidates": [{"content": {"parts": [{"text": '{"x":1}'}]},
                                     "finishReason": "STOP"}],
                    "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 3}}
        with ServidorFalso({("POST", "/v1beta/models/gemini-x:generateContent"):
                            lambda c, h: (200, resposta)}) as s:
            r = ClienteGemini("key", "models/gemini-x", base_url=f"{s.url}/v1beta").conversar(
                [{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
                 {"role": "assistant", "content": "a"}], schema={"type": "object"})
            req = s.recebidas[0]
        self.assertEqual((r.texto, r.tokens_entrada, r.tokens_saida), ('{"x":1}', 12, 3))
        self.assertEqual(req["cabecalhos"]["x-goog-api-key"], "key")
        self.assertEqual(req["corpo"]["contents"][1]["role"], "model")
        self.assertEqual(req["corpo"]["systemInstruction"]["parts"][0]["text"], "s")
        self.assertEqual(req["corpo"]["generationConfig"]["responseMimeType"], "application/json")

    def test_sem_chave_recusa(self):
        with self.assertRaisesRegex(ErroLLM, "GEMINI_API_KEY"):
            ClienteGemini(None, "gemini-x").conversar([])


class TestExtracao(unittest.TestCase):

    def test_json_puro_cercado_ou_com_texto_em_volta(self):
        self.assertEqual(extrair_json('{"a": 1}'), {"a": 1})
        self.assertEqual(extrair_json('Aqui:\n```json\n{"a": 2}\n```\nfim'), {"a": 2})
        self.assertEqual(extrair_json('Claro! {"a": 3} espero ajudar'), {"a": 3})
        with self.assertRaises(ErroLLM):
            extrair_json("nao tem json aqui")

    def test_json_com_apenas_fecho_externo_ausente_e_recuperado(self):
        texto = '{"causa":"testbench","evidencias":["reset nao aplicado"]'
        self.assertEqual(extrair_json(texto), {
            "causa": "testbench", "evidencias": ["reset nao aplicado"],
        })
        with self.assertRaises(ErroLLM):
            extrair_json('{"causa":"testbench","evidencias":["incompleta]')

    def test_vhdl_pega_o_maior_bloco_com_entity(self):
        texto = ("Explicacao.\n```vhdl\nlibrary ieee;\n```\n"
                 "```vhdl\nentity alu is\nend alu;\narchitecture rtl of alu is\n"
                 "begin\nend rtl;\n```\n")
        vhdl = extrair_vhdl(texto)
        self.assertTrue(vhdl.startswith("entity alu is"))
        self.assertTrue(vhdl.endswith("end rtl;\n"))

    def test_vhdl_sem_cerca_so_se_parecer_arquivo(self):
        self.assertIsNotNone(extrair_vhdl("entity x is end x; architecture a of x is begin end a;"))
        self.assertIsNone(extrair_vhdl("desculpe, nao consigo"))

    def test_python_exige_cerca_e_decorador_cocotb(self):
        texto = "```python\nimport cocotb\n@cocotb.test()\nasync def t(dut): pass\n```"
        self.assertIn("async def t", extrair_python(texto))
        self.assertIsNone(extrair_python("```python\nprint('nao e teste')\n```"))


class TestConfig(unittest.TestCase):

    def test_env_nao_sobrescreve_o_ambiente(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text("# comentario\nexport RVGEN_MODELO='qwen2.5-coder:7b'\n"
                           "OPENROUTER_API_KEY=\nRVGEN_PROVEDOR=openrouter\n",
                           encoding="utf-8")
            amb = {"RVGEN_PROVEDOR": "ollama"}
            carregadas = carregar_env(env, amb)
        self.assertEqual(carregadas, ["RVGEN_MODELO"])
        self.assertEqual(amb["RVGEN_MODELO"], "qwen2.5-coder:7b")
        self.assertEqual(amb["RVGEN_PROVEDOR"], "ollama")   # o ambiente venceu
        self.assertNotIn("OPENROUTER_API_KEY", amb)          # valor vazio ignorado

    def test_defaults_e_valor_invalido(self):
        cfg = ler_config({}, usar_env_arquivo=False)
        self.assertEqual((cfg.provedor, cfg.executor, cfg.num_ctx),
                         ("ollama", "auto", 16384))
        self.assertIsNone(cfg.modelo)
        # vllm: URL com padrao, chave opcional (None quando ausente)
        self.assertEqual(cfg.vllm_url, "http://localhost:8000/v1")
        self.assertIsNone(cfg.vllm_key)
        with self.assertRaisesRegex(ValueError, "RVGEN_PROVEDOR"):
            ler_config({"RVGEN_PROVEDOR": "gpt"}, usar_env_arquivo=False)

    def test_vllm_por_ambiente(self):
        cfg = ler_config({"RVGEN_PROVEDOR": "vllm",
                          "RVGEN_VLLM_BASE_URL": "http://gpu1:8000/v1/",
                          "RVGEN_VLLM_API_KEY": "tok-1"},
                         usar_env_arquivo=False)
        self.assertEqual(cfg.provedor, "vllm")
        self.assertEqual(cfg.vllm_url, "http://gpu1:8000/v1")   # barra final vai
        self.assertEqual(cfg.vllm_key, "tok-1")
        # vazio = None, igual ao openrouter
        cfg2 = ler_config({"RVGEN_PROVEDOR": "vllm"}, usar_env_arquivo=False)
        self.assertIsNone(cfg2.vllm_key)

    def test_google_por_ambiente(self):
        cfg = ler_config({"RVGEN_PROVEDOR": "google", "GEMINI_API_KEY": "k",
                          "RVGEN_GEMINI_MODEL": "gemini-x"}, usar_env_arquivo=False)
        self.assertEqual((cfg.provedor, cfg.gemini_key, cfg.gemini_modelo), ("google", "k", "gemini-x"))


if __name__ == "__main__":
    unittest.main()
