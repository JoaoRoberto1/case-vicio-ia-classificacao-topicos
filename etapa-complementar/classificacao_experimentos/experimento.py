"""Compara a grade pré-registrada usando somente vetores já preparados."""

from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import re

from classificacao_local.experimento import publicar_produtos, resumir
from classificacao_topicos.avaliacao import tema_aceito
from classificacao_topicos.pipeline import (
    _conferir_existentes, _json, _jsonl, _sha, _validar_saida,
)
from .contexto import (
    assinar, carregar_contexto, conferir_assinaturas, ler_json, ler_jsonl,
)
from .entradas import carregar_cache
from .motor import predizer, treinar, validar_config
from .preparar import FONTES_PREPARACAO


CRITERIO = [
    "acertos_ramo_decrescente", "acertos_exato_decrescente",
    "prioridade_crescente", "receita_id_crescente",
]


def expandir_receitas(config: dict) -> dict:
    if config.get("versao") != 1 or config.get("criterio_selecao") != CRITERIO:
        raise ValueError("Versão ou critério de seleção do experimento inválido.")
    if type(config.get("top_k")) is not int or not 1 <= config["top_k"] <= 20:
        raise ValueError("top_k inválido.")
    limiares = config.get("limiares_diagnosticos_score")
    if (not isinstance(limiares, list) or not limiares
            or any(isinstance(t, bool) or not isinstance(t, (int, float))
                   or not math.isfinite(t) or not 0 <= t <= 1 for t in limiares)
            or sorted(set(limiares)) != limiares):
        raise ValueError("Limiares diagnósticos inválidos.")
    receitas, prioridades = {}, set()
    if not isinstance(config.get("receitas"), dict) or not config["receitas"]:
        raise ValueError("Receitas ausentes.")
    for nome, r in sorted(config["receitas"].items()):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", nome):
            raise ValueError("Nome de receita inválido.")
        prioridade = r.get("prioridade")
        if type(prioridade) is not int or prioridade < 0 or prioridade in prioridades:
            raise ValueError("Prioridades devem ser inteiras, não negativas e únicas.")
        prioridades.add(prioridade)
        parametros = {
            "modo": r["modo"], "peso_exemplos": r["peso_exemplos"],
            "peso_leis": r["peso_leis"], "vizinhos": r["vizinhos"],
            "rrf_k": config["rrf_k"], "peso_semantico": config["peso_semantico"],
            "lexical": {**config["lexical_base"], **r.get("lexical_pesos", {})},
        }
        receitas[nome] = validar_config(parametros)
    return receitas


def avaliar_predicao(p: dict, r: dict, taxonomia: dict, vistos: set[str]) -> dict:
    return {
        **p,
        "acertos": {m: tema_aceito(p["tema_sugerido_id"], r, taxonomia, m)
                    for m in ("ramo", "imediato", "exato")},
        "acerto_top_k_ramo": any(
            tema_aceito(t["tema_id"], r, taxonomia) for t in p["top_candidatos"]),
        "referencia_fora": r["fora_da_taxonomia"],
        "disciplina_referencia": r["disciplina"],
        "central_visto_treino": r["tema_central_id"] in vistos,
    }


def medir(resultados: list[dict], limiares: list[float]) -> dict:
    return {
        "geral": resumir(resultados),
        "dentro_taxonomia": resumir([p for p in resultados if not p["referencia_fora"]]),
        "fora_taxonomia": resumir([p for p in resultados if p["referencia_fora"]]),
        "por_disciplina": {
            d: resumir([p for p in resultados if p["disciplina_referencia"] == d])
            for d in sorted({p["disciplina_referencia"] for p in resultados})
        },
        "por_particao_interna": {
            str(i): resumir([p for p in resultados if p["particao_interna"] == i])
            for i in sorted({p["particao_interna"] for p in resultados})
        },
        "central_visto_treino": resumir(
            [p for p in resultados if p["central_visto_treino"]]),
        "central_nao_visto_treino_dentro_taxonomia": resumir([
            p for p in resultados
            if not p["central_visto_treino"] and not p["referencia_fora"]]),
        "curva_diagnostica_score": [
            {"limiar": t, "fracao_retida": len(retidos) / len(resultados),
             **resumir(retidos)}
            for t in limiares
            for retidos in [[p for p in resultados
                             if p["score"] >= t and not p["sem_evidencia"]]]
        ],
    }


def processar_experimento(
    questoes: list[dict], rotulos: list[dict], taxonomia: dict,
    protocolo: dict, config: dict, cache: dict, progresso=None,
) -> tuple[dict[str, bytes], dict]:
    receitas = expandir_receitas(config)
    qs = {q["id"]: q for q in questoes}
    rs = {r["id"]: r for r in rotulos}
    dev = set(protocolo["desenvolvimento_ids"])
    reserva = set(protocolo["reserva_ids"])
    avaliacao = set(protocolo["avaliacao_ids"])
    if (len(qs) != len(questoes) or len(rs) != len(rotulos)
            or dev & reserva or (dev | reserva) & avaliacao
            or set(qs) != dev | reserva | avaliacao or set(rs) != dev | reserva
            or set(cache["questoes"]) != dev | avaliacao):
        raise ValueError("Dados/cache não correspondem à separação de desenvolvimento e reserva.")
    qs = {i: q for i, q in qs.items() if i not in reserva}
    rs = {i: rs[i] for i in sorted(dev)}
    predicoes, metricas = [], {}
    ordem = sorted(receitas, key=lambda n: (config["receitas"][n]["prioridade"], n))
    for nome in ordem:
        resultados = []
        for fold in protocolo["particoes_internas"]:
            treino, validacao = fold["treino_ids"], fold["validacao_ids"]
            if (len(set(treino)) != len(treino) or len(set(validacao)) != len(validacao)
                    or set(treino) & set(validacao)
                    or set(treino) | set(validacao) != dev):
                raise ValueError("Partição interna contém repetição, vazamento ou reserva.")
            modelo = treinar([qs[i] for i in treino], [rs[i] for i in treino],
                             taxonomia, receitas[nome], cache)
            vistos = {rs[i]["tema_central_id"] for i in treino
                      if not rs[i]["fora_da_taxonomia"]}
            for identificador in validacao:
                p = predizer(modelo, qs[identificador], cache, top_k=config["top_k"])
                p = avaliar_predicao(p, rs[identificador], taxonomia, vistos)
                p.update({"receita": nome, "particao_interna": fold["indice"]})
                resultados.append(p)
        if Counter(p["id"] for p in resultados) != Counter({i: 1 for i in dev}):
            raise ValueError("Cada referência deve receber uma predição fora da amostra por receita.")
        resultados.sort(key=lambda p: p["id"])
        predicoes.extend(resultados)
        metricas[nome] = medir(resultados, config["limiares_diagnosticos_score"])
        if progresso:
            # O progresso não mostra rótulos, conteúdo ou predições individuais.
            progresso(nome)
    selecionada = min(receitas, key=lambda n: (
        -metricas[n]["geral"]["acertos"]["ramo"],
        -metricas[n]["geral"]["acertos"]["exato"],
        config["receitas"][n]["prioridade"], n,
    ))
    modelo = treinar([qs[i] for i in sorted(dev)], [rs[i] for i in sorted(dev)],
                     taxonomia, receitas[selecionada], cache)
    modelo_bytes = _json(modelo)
    modelo = json.loads(modelo_bytes)
    sugestoes = [
        {**predizer(modelo, qs[i], cache, top_k=config["top_k"]),
         "receita": selecionada, "uso": "sugestao_intermediaria"}
        for i in sorted(avaliacao)
    ]
    relatorio = {
        "versao": 1, "receita_selecionada": selecionada,
        "criterio_selecao": config["criterio_selecao"],
        "natureza": "Desenvolvimento exploratório nas mesmas 80 referências; seleção usa estas métricas.",
        "reservados_sem_vetor_ou_predicao": len(reserva),
        "questoes_avaliacao_sem_rotulo": len(avaliacao),
        "score_e_probabilidade": False, "curva_define_publicacao": False,
        "top_k": config["top_k"],
        "referencias_desenvolvimento": {
            "total": len(dev), "fora": sum(r["fora_da_taxonomia"] for r in rs.values()),
            "centrais_distintos": len({r["tema_central_id"] for r in rs.values()
                                      if not r["fora_da_taxonomia"]}),
        },
        "receitas": metricas,
    }
    congelamento = {
        "versao": 1, "receita": selecionada,
        "parametros": receitas[selecionada],
        "criterio_selecao": config["criterio_selecao"],
        "cache_sha256": cache["sha256"],
        "treino_ids": sorted(dev), "reserva_ids": sorted(reserva),
        "classificador_congelado_para_modulo4": True,
        "calibrador_e_politica_congelados": False,
        "proximo_passo": "Calibrar e congelar política usando desenvolvimento; só depois abrir a reserva.",
    }
    produtos = {
        "protocolo.json": _json(protocolo),
        "metricas_desenvolvimento.json": _json(relatorio),
        "predicoes_desenvolvimento.jsonl": _jsonl(predicoes),
        "sugestoes_avaliacao.jsonl": _jsonl(sugestoes),
        "modelo_selecionado.json": modelo_bytes,
        "receita_congelada.json": _json(congelamento),
    }
    return produtos, {
        "receita_selecionada": selecionada,
        "acertos_ramo_desenvolvimento": metricas[selecionada]["geral"]["acertos"]["ramo"],
        "desenvolvimento": len(dev), "reserva_sem_vetor_ou_predicao": len(reserva),
        "predicoes_desenvolvimento": len(predicoes), "sugestoes": len(sugestoes),
    }


def _conferir_baselines(raiz: Path, predicoes: list[dict]) -> None:
    anteriores = {
        (p["receita"], p["id"]): p
        for p in ler_jsonl(raiz, "artefatos/lexical-v1/predicoes_desenvolvimento.jsonl")
    }
    mapa = {"lexical_m2": "lexical", "lexical_leis_m2": "lexical_leis"}
    for p in predicoes:
        if p["receita"] not in mapa:
            continue
        anterior = anteriores[(mapa[p["receita"]], p["id"])]
        campos = ("tema_sugerido_id", "score", "margem", "acertos", "acerto_top_k_ramo")
        if any(p[c] != anterior[c] for c in campos):
            raise ValueError("A receita de referência não reproduziu o módulo 2.")
        if [(t["tema_id"], t["score"]) for t in p["top_candidatos"]] != [
            (t["tema_id"], t["score"]) for t in anterior["top_candidatos"]
        ]:
            raise ValueError("Ranking da referência divergente do módulo 2.")


def construir_produtos(raiz: Path, diretorio_cache: Path) -> tuple[dict[str, bytes], dict]:
    raiz = raiz.resolve()
    contexto = carregar_contexto(raiz)
    config = ler_json(raiz, "config/modulo3/experimento.json")
    config_embeddings = ler_json(raiz, "config/modulo3/embeddings.json")
    cache, manifesto_cache = carregar_cache(
        diretorio_cache, contexto["registros"], config_embeddings,
    )
    if manifesto_cache["fontes_preparacao_sha256"] != assinar(raiz, FONTES_PREPARACAO):
        raise ValueError("Proveniência do cache incompleta ou divergente da preparação fixada.")
    caminhos = [
        *[p.relative_to(raiz).as_posix()
          for p in (raiz / "classificacao_experimentos").glob("*.py")],
        *[p.relative_to(raiz).as_posix()
          for p in (raiz / "config/modulo3").glob("*.json")],
        (diretorio_cache / "vetores.json").relative_to(raiz).as_posix(),
        (diretorio_cache / "manifesto.json").relative_to(raiz).as_posix(),
        "artefatos/preparacao/manifesto.json",
        "artefatos/lexical-v1/manifesto.json",
    ]
    assinaturas = assinar(raiz, caminhos)
    produtos, resumo = processar_experimento(
        contexto["questoes"],
        ler_jsonl(raiz, "artefatos/preparacao/rotulos_referencia.jsonl"),
        contexto["taxonomia"], contexto["protocolo"], config, cache,
        progresso=lambda n: print(f"Receita concluída: {n}", flush=True),
    )
    # A preparação emite uma linha física por registro, mesmo quando o texto
    # contém separadores Unicode. Não usar splitlines().
    predicoes = [json.loads(linha) for linha in
                 produtos["predicoes_desenvolvimento.jsonl"].decode("utf-8").split("\n")[:-1]]
    _conferir_baselines(raiz, predicoes)
    produtos["manifesto.json"] = _json({
        "versao": 1, "procedimento": "comparacao-lexical-semantica-v1",
        "entradas_e_implementacao_sha256": assinaturas,
        "fontes_fixadas": contexto["fontes_fixadas"],
        "cache_vetores_sha256": cache["sha256"],
        "produtos_sha256": {n: _sha(b) for n, b in produtos.items()},
        "receita_selecionada": resumo["receita_selecionada"],
        "origem_rotulos": "anexos/folha_verdade.csv",
        "modelo_linguagem_na_preparacao": config_embeddings["modelo"],
        "modelo_linguagem_na_classificacao": False,
        "rede_necessaria_na_classificacao": False,
        "baselines_m2_reproduzidos": True,
        "reserva_vetorizada_ou_avaliada": False,
    })
    conferir_assinaturas(raiz, assinaturas)
    return produtos, resumo


def executar_experimento(
    raiz: Path, saida: Path, cache: Path, verificar: bool = False,
) -> dict:
    saida = _validar_saida(raiz, saida)
    cache = _validar_saida(raiz, cache)
    if saida == cache or saida.is_relative_to(cache) or cache.is_relative_to(saida):
        raise ValueError("Saída do classificador e cache precisam ser diretórios separados.")
    produtos, resumo = construir_produtos(raiz, cache)
    if verificar:
        _conferir_existentes(saida, produtos, exigir_completo=True)
    else:
        publicar_produtos(saida, produtos)
    return resumo
