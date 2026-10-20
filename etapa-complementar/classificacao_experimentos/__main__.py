"""Preparação explícita de embeddings e experimentos locais separados."""

import argparse
import json
from pathlib import Path
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=(
        "baixar-modelo", "preparar-embeddings", "experimentar", "verificar",
    ))
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--cache", type=Path, default=Path("artefatos/embeddings-e5-v1"))
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parents[1]
    inicio = time.perf_counter()
    try:
        if args.comando == "baixar-modelo":
            from .contexto import ler_json
            from .download_modelo import baixar_modelo
            resultado = baixar_modelo(raiz, ler_json(raiz, "config/modulo3/embeddings.json"))
        elif args.comando == "preparar-embeddings":
            from .preparar import preparar_embeddings
            ultimo = [0.0]
            def progresso(processados, total):
                agora = time.monotonic()
                if processados == total or agora - ultimo[0] >= 15:
                    print(f"Janelas vetorizadas: {processados}/{total}", flush=True)
                    ultimo[0] = agora
            resultado = preparar_embeddings(
                raiz, args.saida or Path("artefatos/embeddings-e5-v1"), progresso,
            )
        else:
            from .experimento import executar_experimento
            resultado = executar_experimento(
                raiz, args.saida or Path("artefatos/melhorias-v1"), args.cache,
                verificar=args.comando == "verificar",
            )
    except (ValueError, OSError, KeyError, TypeError, ImportError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(json.dumps({"comando": args.comando,
                      "segundos": round(time.perf_counter() - inicio, 3),
                      **resultado}, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
