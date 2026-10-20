"""Combina sinais numéricos locais; não carrega encoders nem usa rede.

Os vetores são entradas previamente calculadas e verificadas. Este módulo
somente calcula cossenos, ranks, RRF e apoio dos exemplos humanos de treino.
Os escores não são probabilidades, nem decisões de publicação ou de ``fora``.
"""

from __future__ import annotations

import hashlib
import json
import math

from classificacao_local import classificador as lexical

from .entradas import hash_texto


SCHEMA = "classificador_hibrido_m3_v1"
_PADRAO = {
    "modo": "hibrido",
    "peso_exemplos": 0.3,
    "vizinhos": "lexicais",
    "peso_leis": 0.0,
    "rrf_k": 20,
    "peso_semantico": 0.5,
}


def validar_config(config: dict) -> dict:
    """Normaliza a receita e recusa parâmetros ignorados ou contraditórios."""
    if not isinstance(config, dict) or set(config) - {*_PADRAO, "lexical"}:
        raise ValueError("Configuração M3 inválida ou com parâmetros desconhecidos.")
    resultado = {**_PADRAO, **config}
    resultado["lexical"] = lexical.validar_config(config.get("lexical", {}))
    if resultado["modo"] not in {"lexical", "semantico", "hibrido"}:
        raise ValueError("modo deve ser lexical, semantico ou hibrido.")
    if resultado["vizinhos"] not in {"lexicais", "semanticos"}:
        raise ValueError("vizinhos deve ser lexicais ou semanticos.")
    for campo in ("peso_exemplos", "peso_leis", "peso_semantico"):
        valor = resultado[campo]
        if (isinstance(valor, bool) or not isinstance(valor, (float, int))
                or not math.isfinite(valor) or not 0 <= valor <= 1):
            raise ValueError(f"{campo} deve ser número finito entre zero e um.")
        resultado[campo] = float(valor)
    if resultado["peso_exemplos"] + resultado["peso_leis"] > 1:
        raise ValueError("A soma dos pesos de exemplos e leis não pode ultrapassar um.")
    if type(resultado["rrf_k"]) is not int or not 1 <= resultado["rrf_k"] <= 10000:
        raise ValueError("rrf_k deve ser inteiro entre um e dez mil.")
    if resultado["modo"] == "semantico" and (
        resultado["peso_exemplos"] or resultado["peso_leis"]
    ):
        raise ValueError("A ablação semântica pura exige exemplos e leis com peso zero.")
    if resultado["modo"] == "lexical":
        if resultado["vizinhos"] != "lexicais":
            raise ValueError("O modo lexical delega somente aos vizinhos lexicais.")
        for campo in ("peso_exemplos", "peso_leis"):
            if resultado[campo] != resultado["lexical"][campo]:
                raise ValueError(f"{campo} deve coincidir com a configuração lexical.")
    return resultado


def _sha_valido(valor: object) -> bool:
    return (isinstance(valor, str) and len(valor) == 64
            and all(letra in "0123456789abcdef" for letra in valor))


def _metadados_cache(cache: dict) -> tuple[str, int]:
    if not isinstance(cache, dict) or not _sha_valido(cache.get("sha256")):
        raise ValueError("O cache precisa de sha256 válido, conferido pelo carregador.")
    dimensoes = cache.get("dimensoes")
    if type(dimensoes) is not int or dimensoes < 1:
        raise ValueError("O cache deve informar dimensoes como inteiro positivo.")
    for campo in ("questoes", "temas"):
        if not isinstance(cache.get(campo), dict):
            raise ValueError(f"O cache deve conter o índice {campo}.")
    return cache["sha256"], dimensoes


def _hash_vetor(vetor: list) -> str:
    return hashlib.sha256(json.dumps(
        vetor, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _entrada_cache(
    cache: dict, grupo: str, identificador: str, esperado: str,
    referencia: dict | None = None,
) -> list:
    entrada = cache[grupo].get(identificador)
    if not isinstance(entrada, dict) or entrada.get("texto_sha256") != esperado:
        raise ValueError(f"Texto ausente ou divergente no cache: {grupo}/{identificador}.")
    vetor = entrada.get("vetor")
    if (not isinstance(vetor, list) or len(vetor) != cache["dimensoes"]
            or any(isinstance(valor, bool) or not isinstance(valor, (int, float))
                   or not math.isfinite(valor) for valor in vetor)):
        raise ValueError(f"Vetor inválido no cache: {grupo}/{identificador}.")
    norma_quadrada = math.fsum(valor * valor for valor in vetor)
    if not math.isclose(norma_quadrada, 1.0, rel_tol=0.0, abs_tol=1e-5):
        raise ValueError(f"Vetor do cache não normalizado: {grupo}/{identificador}.")
    if referencia is not None and _hash_vetor(vetor) != referencia["vetor_sha256"]:
        raise ValueError(f"Vetor divergente do treino: {grupo}/{identificador}.")
    return vetor


def _referencia(cache: dict, grupo: str, identificador: str, texto_hash: str) -> dict:
    vetor = _entrada_cache(cache, grupo, identificador, texto_hash)
    return {"texto_sha256": texto_hash, "vetor_sha256": _hash_vetor(vetor)}


def _cos(esquerda: list, direita: list) -> float:
    # A divisão pelas normas corrige o arredondamento do cache sem supor que
    # norma numericamente próxima de um seja exatamente um.
    produto = math.fsum(a * b for a, b in zip(esquerda, direita))
    normas = math.sqrt(
        math.fsum(a * a for a in esquerda) * math.fsum(b * b for b in direita)
    )
    return min(1.0, max(0.0, produto / normas))


def treinar(
    questoes_treino: list[dict], rotulos_treino: list[dict],
    taxonomia: dict, config: dict, cache: dict,
) -> dict:
    """Ajusta o lexical e vincula somente o catálogo e o treino fornecido."""
    configuracao = validar_config(config)
    cache_sha, dimensoes = _metadados_cache(cache)
    modelo_lexical = lexical.treinar(
        questoes_treino, rotulos_treino, taxonomia, configuracao["lexical"],
    )
    referencias = {"temas": {}, "questoes_treino": {}}
    if configuracao["modo"] != "lexical":
        for tema in modelo_lexical["catalogo"]:
            identificador = tema["tema_id"]
            referencias["temas"][identificador] = _referencia(
                cache, "temas", identificador,
                hash_texto("tema", taxonomia["por_id"][identificador]),
            )
        for questao in sorted(questoes_treino, key=lambda registro: registro["id"]):
            referencias["questoes_treino"][questao["id"]] = _referencia(
                cache, "questoes", questao["id"], hash_texto("questao", questao),
            )
    modelo = {
        "schema": SCHEMA,
        "config": configuracao,
        "cache_sha256": cache_sha,
        "dimensoes": dimensoes,
        "lexical": modelo_lexical,
        "referencias_cache": referencias,
    }
    validar_modelo(modelo)
    return modelo


def validar_modelo(modelo: dict, *, verificar_lexical: bool = True) -> None:
    """Valida o JSON sem abrir arquivos nem depender de estado de processo.

    A predição omite somente a inspeção profunda do submodelo: o próprio
    ``lexical.predizer`` a executa antes de calcular qualquer sinal.
    """
    if not isinstance(modelo, dict) or set(modelo) != {
        "schema", "config", "cache_sha256", "dimensoes", "lexical",
        "referencias_cache",
    } or modelo["schema"] != SCHEMA:
        raise ValueError("Esquema de modelo M3 inválido.")
    if not _sha_valido(modelo["cache_sha256"]):
        raise ValueError("Assinatura de cache inválida no modelo.")
    if type(modelo["dimensoes"]) is not int or modelo["dimensoes"] < 1:
        raise ValueError("Dimensionalidade inválida no modelo.")
    config = validar_config(modelo["config"])
    if modelo["config"] != config:
        raise ValueError("Configuração serializada M3 deve estar completa.")
    submodelo = modelo["lexical"]
    if verificar_lexical:
        lexical.validar_modelo(submodelo)
    elif (
        not isinstance(submodelo, dict)
        or not isinstance(submodelo.get("config"), dict)
        or not isinstance(submodelo.get("catalogo"), list)
        or not isinstance(submodelo.get("treino"), list)
        or any(not isinstance(item, dict) or not isinstance(item.get(campo), str)
               for grupo, campo in (("catalogo", "tema_id"), ("treino", "id"))
               for item in submodelo[grupo])
    ):
        raise ValueError("Metadados do submodelo lexical inválidos.")
    if config["lexical"] != submodelo["config"]:
        raise ValueError("Configuração lexical divergente do submodelo.")
    referencias = modelo["referencias_cache"]
    if not isinstance(referencias, dict) or set(referencias) != {
        "temas", "questoes_treino",
    }:
        raise ValueError("Referências do cache inválidas.")
    esperados = {
        "temas": {item["tema_id"] for item in modelo["lexical"]["catalogo"]},
        "questoes_treino": {item["id"] for item in modelo["lexical"]["treino"]},
    }
    for grupo, ids in esperados.items():
        valores = referencias[grupo]
        if not isinstance(valores, dict) or set(valores) != (
            ids if config["modo"] != "lexical" else set()
        ):
            raise ValueError("Referências do cache não correspondem ao catálogo/treino.")
        for referencia in valores.values():
            if (not isinstance(referencia, dict) or set(referencia) != {
                "texto_sha256", "vetor_sha256",
            } or not all(_sha_valido(valor) for valor in referencia.values())):
                raise ValueError("Assinatura de referência inválida.")


def _diagnosticos_vizinhos(vizinhos: list[dict]) -> dict:
    return {
        "similaridade_maxima_vizinho": max(
            (item["similaridade"] for item in vizinhos), default=0.0,
        ),
        "soma_similaridades_quadradas": math.fsum(
            item["similaridade"] ** 2 for item in vizinhos
        ),
        "quantidade_vizinhos": len(vizinhos),
    }


def _apoio_semantico(modelo: dict, vetor: list, vetores_treino: dict) -> tuple:
    referencias = modelo["referencias_cache"]["questoes_treino"]
    proximos = [
        (_cos(vetor, vetores_treino[exemplo["id"]]), exemplo)
        for exemplo in modelo["lexical"]["treino"]
    ]
    proximos = [(sim, exemplo) for sim, exemplo in proximos if sim > 0]
    proximos.sort(key=lambda item: (
        -item[0], referencias[item[1]["id"]]["texto_sha256"],
        item[1]["fora_da_taxonomia"], item[1]["tema_central_id"],
        tuple(item[1]["extras_ids"]),
    ))
    proximos = proximos[:3]
    denominador = math.fsum(sim * sim for sim, _ in proximos)
    contribuicoes: dict[str, list[float]] = {}
    fora = []
    if denominador:
        for sim, exemplo in proximos:
            peso = sim * sim / denominador
            if exemplo["fora_da_taxonomia"]:
                fora.append(peso)
            else:
                contribuicoes.setdefault(exemplo["tema_central_id"], []).append(peso)
                for extra in exemplo["extras_ids"]:
                    contribuicoes.setdefault(extra, []).append(0.5 * peso)
    apoios = {
        tema_id: min(1.0, math.fsum(pesos))
        for tema_id, pesos in contribuicoes.items()
    }
    vizinhos = [
        {"id": exemplo["id"], "similaridade": sim}
        for sim, exemplo in proximos
    ]
    return apoios, min(1.0, math.fsum(fora)), vizinhos


def predizer(modelo: dict, questao: dict, cache: dict, top_k: int = 5) -> dict:
    """Ordena temas com entradas congeladas, sem inferência de encoder/LLM."""
    validar_modelo(modelo, verificar_lexical=False)
    cache_sha, dimensoes = _metadados_cache(cache)
    if cache_sha != modelo["cache_sha256"] or dimensoes != modelo["dimensoes"]:
        raise ValueError("O cache diverge da assinatura/dimensionalidade do modelo.")
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k deve ser inteiro positivo.")
    # O motor M2 também valida a questão e recusa seu ID se pertencente ao treino.
    resultado_lexical = lexical.predizer(
        modelo["lexical"], questao, top_k=len(modelo["lexical"]["catalogo"]),
    )
    config = modelo["config"]
    if config["modo"] == "lexical":
        resultado_lexical["top_candidatos"] = resultado_lexical["top_candidatos"][:top_k]
        return {
            **resultado_lexical,
            **_diagnosticos_vizinhos(resultado_lexical["vizinhos"]),
        }
    vetor = _entrada_cache(
        cache, "questoes", questao["id"], hash_texto("questao", questao),
    )
    referencias = modelo["referencias_cache"]
    vetores_temas = {
        identificador: _entrada_cache(
            cache, "temas", identificador, referencia["texto_sha256"], referencia,
        )
        for identificador, referencia in referencias["temas"].items()
    }
    vetores_treino = {
        identificador: _entrada_cache(
            cache, "questoes", identificador, referencia["texto_sha256"], referencia,
        )
        for identificador, referencia in referencias["questoes_treino"].items()
    }
    lexicais = {
        item["tema_id"]: item for item in resultado_lexical["top_candidatos"]
    }
    semanticos = {
        identificador: _cos(vetor, valores)
        for identificador, valores in vetores_temas.items()
    }
    ranks_lexicais = {
        identificador: rank for rank, identificador in enumerate(sorted(
            lexicais,
            key=lambda tema_id: (-lexicais[tema_id]["similaridade_catalogo"], tema_id),
        ), 1)
    }
    ranks_semanticos = {
        identificador: rank for rank, identificador in enumerate(sorted(
            semanticos, key=lambda tema_id: (-semanticos[tema_id], tema_id),
        ), 1)
    }
    if config["modo"] == "semantico":
        apoios, apoio_fora, vizinhos = {}, 0.0, []
    elif config["vizinhos"] == "semanticos":
        apoios, apoio_fora, vizinhos = _apoio_semantico(modelo, vetor, vetores_treino)
    else:
        apoios = {tema_id: item["apoio_exemplos"] for tema_id, item in lexicais.items()}
        apoio_fora, vizinhos = resultado_lexical["apoio_fora"], resultado_lexical["vizinhos"]
    candidatos = []
    peso_catalogo = 1.0 - config["peso_exemplos"] - config["peso_leis"]
    for tema_id in sorted(lexicais):
        original = lexicais[tema_id]
        if config["modo"] == "semantico":
            catalogo = semanticos[tema_id]
        else:
            k, peso_semantico = config["rrf_k"], config["peso_semantico"]
            catalogo = math.fsum([
                (1 - peso_semantico) * (k + 1) / (k + ranks_lexicais[tema_id]),
                peso_semantico * (k + 1) / (k + ranks_semanticos[tema_id]),
            ])
        apoio = apoios.get(tema_id, 0.0)
        score = math.fsum([
            peso_catalogo * catalogo,
            config["peso_exemplos"] * apoio,
            config["peso_leis"] * original["evidencia_leis"],
        ])
        candidatos.append({
            **original,
            "score": min(1.0, max(0.0, score)),
            "similaridade_semantica": semanticos[tema_id],
            "rank_lexical": ranks_lexicais[tema_id],
            "rank_semantico": ranks_semanticos[tema_id],
            "score_catalogo": catalogo,
            "apoio_exemplos": apoio,
        })
    candidatos.sort(key=lambda item: (-item["score"], item["tema_id"]))
    melhor = candidatos[0]
    evidencia_catalogo = melhor["similaridade_semantica"] > 0
    if config["modo"] == "hibrido":
        evidencia_catalogo = (
            (config["peso_semantico"] > 0 and evidencia_catalogo)
            or (config["peso_semantico"] < 1 and melhor["similaridade_catalogo"] > 0)
        )
    tem_evidencia = (
        (peso_catalogo > 0 and evidencia_catalogo)
        or (config["peso_exemplos"] > 0 and melhor["apoio_exemplos"] > 0)
        or (config["peso_leis"] > 0 and melhor["evidencia_leis"] > 0)
    )
    return {
        "id": questao["id"],
        "tema_sugerido_id": melhor["tema_id"],
        "score": melhor["score"],
        "margem": melhor["score"] - (candidatos[1]["score"] if len(candidatos) > 1 else 0),
        "sem_evidencia": not tem_evidencia,
        "apoio_fora": apoio_fora,
        "top_candidatos": candidatos[:top_k],
        "vizinhos": vizinhos,
        **_diagnosticos_vizinhos(vizinhos),
    }
