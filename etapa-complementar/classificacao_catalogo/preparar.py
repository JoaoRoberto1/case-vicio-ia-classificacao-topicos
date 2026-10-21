"""Única entrada M7 que pode executar encoder: prepara só os temas do catálogo."""

import hashlib
from pathlib import Path

from classificacao_experimentos.contexto import carregar_contexto, ler_json, assinar
from classificacao_experimentos.entradas import construir_registros, validar_cache
from classificacao_topicos.pipeline import _json
from .catalogo import ARQUIVOS, carregar

PASTA = "artefatos/catalogo-m7-embeddings"


def executar(raiz: Path):
    # Importação deliberadamente exclusiva da preparação. A decisão não a importa.
    from classificacao_experimentos.preparacao_embeddings import gerar_cache
    contexto = carregar_contexto(raiz)
    taxonomia = carregar(raiz, contexto["taxonomia"])
    config = ler_json(raiz, "config/modulo3/embeddings.json")
    modelo = raiz / ".cache-modelos/e5-small"
    for nome, info in config["arquivos"].items():
        p = modelo / nome
        if p.stat().st_size != info["bytes"] or hashlib.sha256(p.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError("Modelo local difere do encoder fixado no M3.")
    entradas = construir_registros([], taxonomia["registros"], set())
    cache, diagnostico = gerar_cache(entradas, config["preparacao"],
                                    modelo / "modelo.onnx", modelo / "tokenizer.json",
                                    lambda n, total: print(f"Temas preparados: {n}/{total}", flush=True) if n % 80 == 0 or n == total else None)
    validar_cache(cache, entradas)
    dados = _json(cache)
    manifesto = {"schema": "cache_catalogo_m7_v1", "configuracao_encoder": config,
                 "fontes_sha256": assinar(raiz, ARQUIVOS + [
                     "config/modulo7/protocolo.json", "classificacao_catalogo/catalogo.py",
                     "classificacao_catalogo/preparar.py", "config/modulo3/embeddings.json",
                     "classificacao_experimentos/preparacao_embeddings.py",
                     "classificacao_experimentos/entradas.py", "artefatos/preparacao/temas_preparados.json"]),
                 "diagnostico": diagnostico, "questoes_novas_vetorizadas": 0,
                 "produtos_sha256": {"vetores.json": hashlib.sha256(dados).hexdigest()},
                 "llm_decide_classificacoes": False}
    destino = raiz / PASTA
    destino.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in {"vetores.json": dados, "manifesto.json": _json(manifesto)}.items():
        p = destino / nome
        if p.exists() and p.read_bytes() != conteudo:
            raise ValueError("Cache existente diferente: crie outra versão, não sobrescreva.")
        p.write_bytes(conteudo)
    print("Cache M7 preparado e validado.", flush=True)
