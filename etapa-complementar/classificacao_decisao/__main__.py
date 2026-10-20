"""Comandos do módulo 4. Preparação do encoder é uma operação explícita."""

import argparse
import json
from pathlib import Path
import sys
import time


def _bloquear_operacoes(preparacao: bool) -> None:
    """Rede e .env ficam bloqueados; só a preparação pode carregar o encoder."""
    dependencias = {
        "numpy", "onnxruntime", "tokenizers", "torch", "transformers",
        "sentence_transformers", "huggingface_hub",
    }

    def guard(evento, argumentos):
        if evento in {"socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("Rede bloqueada nos comandos do módulo 4.")
        if not preparacao and evento == "import" and argumentos:
            if argumentos[0].split(".")[0] in dependencias:
                raise RuntimeError("Codificador proibido na classificação e verificação.")
        if evento == "open" and argumentos and isinstance(argumentos[0], (str, bytes)):
            nome = argumentos[0].decode() if isinstance(argumentos[0], bytes) else argumentos[0]
            caminho = Path(nome)
            if caminho.name == ".env" or caminho.name.startswith(".env."):
                raise RuntimeError("Leitura de credenciais bloqueada.")
            if not preparacao and ".cache-modelos" in caminho.parts:
                raise RuntimeError("Pesos proibidos na classificação e verificação.")
    sys.addaudithook(guard)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=[
        "calibrar", "verificar-calibracao", "preparar-reserva",
        "avaliar-reserva", "verificar-reserva", "regenerar", "verificar",
    ])
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parent.parent
    inicio = time.perf_counter()
    _bloquear_operacoes(args.comando == "preparar-reserva")
    try:
        if args.comando in {"calibrar", "verificar-calibracao"}:
            from .desenvolvimento import executar_calibracao
            resultado = executar_calibracao(raiz, args.comando == "verificar-calibracao")
        elif args.comando == "preparar-reserva":
            from .cache import preparar_reserva
            from .desenvolvimento import CACHE, selo_congelamento
            caminho, sha = selo_congelamento(raiz)
            resultado = preparar_reserva(raiz, raiz / CACHE, caminho, sha)
        elif args.comando in {"avaliar-reserva", "verificar-reserva"}:
            from .execucao import executar_reserva
            resultado = executar_reserva(raiz, args.comando == "verificar-reserva")
        elif args.comando == "regenerar":
            from .execucao import executar_entrega
            resultado = executar_entrega(raiz)
        else:
            from .execucao import verificar_tudo
            resultado = verificar_tudo(raiz)
    except (ValueError, KeyError, TypeError, OSError, ImportError, RuntimeError) as exc:
        parser.exit(1, f"Erro: {exc}\n")
    print(json.dumps({
        "comando": args.comando, "segundos": round(time.perf_counter() - inicio, 3), **resultado,
    }, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
