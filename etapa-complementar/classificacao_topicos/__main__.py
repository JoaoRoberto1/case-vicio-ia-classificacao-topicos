"""Interface de linha de comando da etapa complementar."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .pipeline import executar_preparacao, verificar_preparacao


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preparação e verificação local dos dados do case Vício.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    for nome in ("preparar", "verificar"):
        sub = comandos.add_parser(nome)
        sub.add_argument("--saida", type=Path, default=Path("artefatos/preparacao"),
                         help="Subpasta de artefatos/ ou tmp/ neste repositório.")
    args = parser.parse_args(argv)
    raiz = Path(__file__).resolve().parents[1]
    operacao = executar_preparacao if args.comando == "preparar" else verificar_preparacao
    try:
        resumo = operacao(raiz, args.saida)
    except (OSError, ValueError, KeyError, TypeError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(json.dumps({"operacao": args.comando, "status": "ok",
                      "contagens": resumo}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
