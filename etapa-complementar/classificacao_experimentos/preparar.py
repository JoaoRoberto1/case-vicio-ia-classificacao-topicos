"""Preparação explícita e separada: converte textos em vetores, sem rótulos."""

import hashlib
import importlib.metadata
from pathlib import Path
import platform

from classificacao_local.experimento import publicar_produtos
from classificacao_topicos.pipeline import _json, _sha, _validar_saida
from .contexto import assinar, carregar_contexto, conferir_assinaturas, ler_json
from .entradas import carregar_cache, validar_cache


FONTES_PREPARACAO = [
    "classificacao_experimentos/entradas.py",
    "classificacao_experimentos/contexto.py",
    "classificacao_experimentos/preparar.py",
    "classificacao_experimentos/preparacao_embeddings.py",
    "config/modulo3/embeddings.json",
    "config/modulo3/fontes.json",
    "requirements-preparacao.txt",
    "requirements-preparacao.lock.txt",
    "artefatos/preparacao/manifesto.json",
    "artefatos/lexical-v1/protocolo.json",
]


def preparar_embeddings(raiz: Path, saida: Path, progresso=None) -> dict:
    raiz = raiz.resolve()
    saida = _validar_saida(raiz, saida)
    contexto = carregar_contexto(raiz)
    config = ler_json(raiz, "config/modulo3/embeddings.json")
    assinaturas = assinar(raiz, FONTES_PREPARACAO)
    if saida.exists() and any(saida.iterdir()):
        if {p.name for p in saida.iterdir()} != {"vetores.json", "manifesto.json"}:
            raise ValueError("Cache parcial ou com arquivos inesperados; escolha outra saída.")
        cache, manifesto = carregar_cache(saida, contexto["registros"], config)
        if manifesto["fontes_preparacao_sha256"] != assinaturas:
            raise ValueError("Cache existente foi preparado por outra implementação.")
        return {"reutilizado": True, "questoes": len(cache["questoes"]),
                "temas": len(cache["temas"]), "dimensoes": cache["dimensoes"]}
    # A biblioteca de inferência só é importada nesta operação explícita.
    from .preparacao_embeddings import gerar_cache
    versoes = {nome: importlib.metadata.version(nome)
               for nome in config["dependencias_preparacao"]}
    if versoes != config["dependencias_preparacao"]:
        raise ValueError("Use as versões fixadas das dependências de preparação.")
    pasta = raiz / ".cache-modelos/e5-small"
    for nome, registro in config["arquivos"].items():
        caminho = pasta / nome
        if caminho.is_symlink() or not caminho.is_file():
            raise ValueError("Pesos ausentes; execute baixar-modelo separadamente.")
        with caminho.open("rb") as arquivo:
            sha = hashlib.file_digest(arquivo, "sha256").hexdigest()
        if sha != registro["sha256"] or caminho.stat().st_size != registro["bytes"]:
            raise ValueError("Pesos locais diferentes do modelo fixado.")
    cache, diagnostico = gerar_cache(
        contexto["registros"], config["preparacao"],
        pasta / "modelo.onnx", pasta / "tokenizer.json", progresso=progresso,
    )
    validar_cache(cache, contexto["registros"], config["preparacao"]["dimensoes"])
    produtos = {"vetores.json": _json(cache)}
    produtos["manifesto.json"] = _json({
        "versao": 1,
        "procedimento": "preparacao-e5-small-fp32-v1",
        "configuracao": config,
        "fontes_preparacao_sha256": assinaturas,
        "fontes_fixadas": contexto["fontes_fixadas"],
        "produtos_sha256": {n: _sha(b) for n, b in produtos.items()},
        "ambiente": {
            "python": platform.python_version(),
            "sistema": platform.system(), "arquitetura": platform.machine(),
            "dependencias": versoes,
        },
        "diagnostico": diagnostico,
        "rotulos_fornecidos_ao_codificador": False,
        "modelo_escolheu_temas": False,
        "reserva_vetorizada": False,
        "chamadas_api": 0,
        "custo_api": 0,
    })
    conferir_assinaturas(raiz, assinaturas)
    publicar_produtos(saida, produtos)
    return {"reutilizado": False, "questoes": len(cache["questoes"]),
            "temas": len(cache["temas"]), "dimensoes": cache["dimensoes"],
            "diagnostico": diagnostico}
