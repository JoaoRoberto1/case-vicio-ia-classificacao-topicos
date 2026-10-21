"""Regenera CSV e previsão finais a partir dos anexos e artefatos versionados.

Uso: python -E -X utf8 -B -S scripts/entregar_precisao.py [--verificar]
O experimento completo é refeito; nenhum encoder, peso ou serviço é chamado.
O PDF é editorial e tem geração separada com as dependências opcionais M5.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


def executar(raiz, verificar=False):
    from classificacao_decisao.__main__ import _bloquear_operacoes
    _bloquear_operacoes(False)
    from classificacao_decisao.execucao import _carregar
    from classificacao_precisao.experimento import construir_produtos, SAIDA
    from classificacao_precisao.entrega import construir_entrega
    from classificacao_experimentos.contexto import conferir_assinaturas, ler_json
    inicio = time.perf_counter()
    config = ler_json(raiz, "config/modulo8/protocolo.json")["representacao"]
    if hashlib.sha256((raiz / config["ancoras_arquivo"]).read_bytes()).hexdigest() != config["ancoras_sha256"]:
        raise ValueError("As âncoras divergem da preparação registrada antes das métricas.")
    preparacao = ler_json(raiz, "artefatos/embeddings-e5-large-m8/manifesto.json")
    conferir_assinaturas(raiz, preparacao["fontes_sha256"])
    conferir_assinaturas(raiz, preparacao["fontes_m1_m7_conferidas_sha256"])
    produtos, metricas = construir_produtos(raiz, progresso=lambda s: print(s, flush=True))
    contexto = _carregar(raiz)
    entrega = construir_entrega(produtos, contexto["questoes"], contexto["taxonomia"])
    for pasta, arquivos in ((SAIDA, produtos), ("entrega-final-v2", entrega)):
        destino = raiz / pasta
        if verificar:
            if any(not (destino/n).is_file() or (destino/n).read_bytes() != b for n, b in arquivos.items()):
                raise ValueError("Reprodução divergente em " + pasta)
        else:
            destino.mkdir(parents=True, exist_ok=True)
            if any((destino/n).exists() and (destino/n).read_bytes() != b for n, b in arquivos.items()):
                raise ValueError("Versão existente divergente; não sobrescrever resultados congelados.")
            for n, b in arquivos.items():
                (destino/n).write_bytes(b)
    resultado = {"verificado": verificar, "produtos_experimento": len(produtos),
                 "arquivos_entrega": len(entrega), "questoes": len(contexto["questoes"]),
                 "receita": metricas["receita_selecionada"], "avaliacao559": metricas["avaliacao559"],
                 "encoder_executado": False, "chamadas_api": 0,
                 "segundos": round(time.perf_counter() - inicio, 3)}
    print("ENTREGA_M8=" + json.dumps(resultado, ensure_ascii=True, sort_keys=True), flush=True)
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true")
    argumentos = parser.parse_args()
    executar(RAIZ, argumentos.verificar)


if __name__ == "__main__":
    main()
