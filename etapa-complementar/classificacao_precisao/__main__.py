"""Interface de preparação opcional e reprodução offline M8."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="M8: sinais específicos e confiança seletiva offline")
    parser.add_argument("acao", choices=["executar", "verificar"])
    parser.add_argument("--small", action="store_true", help="Diagnóstico parcial: não abre20 nem exporta559.")
    args = parser.parse_args()
    from classificacao_decisao.__main__ import _bloquear_operacoes
    _bloquear_operacoes(False)
    from .experimento import executar
    executar(Path(__file__).resolve().parents[1], args.acao == "verificar", args.small)


if __name__ == "__main__":
    main()
