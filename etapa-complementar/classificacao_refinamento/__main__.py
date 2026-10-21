"""Executa ou reproduz a rodada exploratória M6 sem rede ou encoder."""

import argparse
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=["executar", "verificar"])
    args = parser.parse_args()
    from classificacao_decisao.__main__ import _bloquear_operacoes
    _bloquear_operacoes(preparacao=False)
    from .experimento import executar
    inicio = time.perf_counter()
    try:
        resultado = executar(Path(__file__).resolve().parent.parent,
            verificar=args.comando == "verificar",
            progresso=lambda mensagem: print(mensagem, flush=True))
    except (ValueError, KeyError, TypeError, OSError, ImportError, RuntimeError) as exc:
        parser.exit(1, f"Erro: {exc}\n")
    print(json.dumps({"comando": args.comando, "segundos": round(time.perf_counter() - inicio, 3),
                      **resultado}, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
