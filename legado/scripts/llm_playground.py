#!/usr/bin/env python3
"""Manda um prompt solto pro modelo configurado via OpenRouter e imprime a resposta.

Uso:
    python scripts/llm_playground.py "seu prompt aqui"
    echo "seu prompt" | python scripts/llm_playground.py

Depende de OPENROUTER_API_KEY em .env (ver .env.example) e, opcionalmente,
SPECHDL_LLM_MODEL (default: openai/gpt-5.6-luna). Não faz parte do pipeline
(fases 1-7) — é só a validação manual do T0.4 (specs/tasks.md).
"""
import os
import sys

from dotenv import load_dotenv
from openrouter import OpenRouter

DEFAULT_MODEL = "openai/gpt-5.6-luna"


def main() -> None:
    load_dotenv()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("OPENROUTER_API_KEY não encontrada. Copie .env.example pra .env e preencha.")

    model = os.environ.get("SPECHDL_LLM_MODEL") or DEFAULT_MODEL

    prompt = " ".join(sys.argv[1:]) or sys.stdin.read().strip()
    if not prompt:
        sys.exit('Nenhum prompt informado. Uso: python scripts/llm_playground.py "seu prompt"')

    with OpenRouter(api_key=api_key) as client:
        response = client.chat.send(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

    print(f"--- modelo: {model} ---")
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
