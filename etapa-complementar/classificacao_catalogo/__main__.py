import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="M7: catálogo enriquecido e experimento seletivo offline")
    parser.add_argument("acao", choices=["preparar", "executar", "verificar"])
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parents[1]
    if args.acao == "preparar":
        from .preparar import executar
        executar(raiz)
    else:
        from .experimento import executar
        executar(raiz, verificar=args.acao == "verificar")


if __name__ == "__main__":
    main()
