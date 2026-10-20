"""CLI offline do primeiro classificador; não gera publicacao.csv."""

import argparse
import json
from pathlib import Path
import sys

from .experimento import executar_experimento


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=("experimentar", "verificar"))
    parser.add_argument("--saida", type=Path, default=Path("artefatos/lexical-v1"))
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parents[1]
    try:
        resultado = executar_experimento(
            raiz, args.saida, verificar=args.comando == "verificar",
        )
    except (ValueError, OSError, KeyError, TypeError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(json.dumps({"comando": args.comando, **resultado},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
