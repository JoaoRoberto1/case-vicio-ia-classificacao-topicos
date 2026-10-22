"""Reconstrói ou verifica a revisão M9, sem API, encoder ou credenciais."""

import argparse
import json
from pathlib import Path
import sys
import time

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true", help="Compara produtos sem sobrescrever; usa preparação autenticada.")
    parser.add_argument("--reconstruir", action="store_true", help="Reexecuta também rankings internos e concordância (vários minutos).")
    args = parser.parse_args()
    from classificacao_decisao.__main__ import _bloquear_operacoes
    _bloquear_operacoes(False)
    from classificacao_politica.preparacao import CACHE, executar_preparacao
    from classificacao_politica.experimento import executar
    inicio = time.perf_counter()
    try:
        if args.reconstruir or not (RAIZ / CACHE / "manifesto.json").exists():
            if args.verificar and not args.reconstruir:
                raise ValueError("Preparação ausente; execute sem --verificar primeiro.")
            executar_preparacao(RAIZ, args.verificar, forcar=args.reconstruir)
        resultado = executar(RAIZ, args.verificar)
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as erro:
        parser.exit(1, f"Erro M9: {erro}\n")
    print(json.dumps({"verificacao": args.verificar, "segundos": round(time.perf_counter()-inicio, 3),
                      **resultado}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
