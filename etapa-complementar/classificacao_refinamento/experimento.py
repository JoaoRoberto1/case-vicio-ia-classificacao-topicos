"""Experimento M6 offline com seleção aninhada e diagnóstico pós-seleção.

As funções de desenvolvimento recebem apenas as80 referências já usadas.
Nada neste pacote decide publicação ou estima precisão entre publicadas.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path

from classificacao_experimentos.contexto import assinar, conferir_assinaturas, ler_json, ler_jsonl
from classificacao_experimentos.experimento import avaliar_predicao
from classificacao_experimentos.motor import treinar, predizer
from classificacao_local.experimento import publicar_produtos, resumir
from classificacao_topicos.pipeline import _json, _jsonl, _conferir_existentes, _validar_saida
from .motor import Motor


SAIDA = "artefatos/refinamento-v1"
CRITERIO = ["acertos_ramo_decrescente", "acertos_exato_decrescente",
            "prioridade_crescente", "receita_id_crescente"]


def _ids(valores):
    if (not isinstance(valores, list) or not valores
            or any(not isinstance(i, str) or not i for i in valores)
            or len(set(valores)) != len(valores)):
        raise ValueError("IDs ausentes, inválidos ou repetidos.")
    return set(valores)


def validar_particoes(folds: list, universo: set, grupos: list) -> None:
    if not isinstance(folds, list) or len(folds) < 2 or not universo:
        raise ValueError("Partições ou universo inválidos.")
    membros, indices, cobertura = set(), set(), Counter()
    for grupo in grupos:
        ids = _ids(grupo["ids"])
        if membros & ids:
            raise ValueError("Grupos sobrepostos.")
        membros.update(ids)
    if not universo <= membros:
        raise ValueError("Grupos não cobrem o universo.")
    for fold in folds:
        indice = fold["indice"]
        if type(indice) is not int or indice in indices:
            raise ValueError("Índice de partição inválido ou repetido.")
        indices.add(indice)
        treino, validacao = _ids(fold["treino_ids"]), _ids(fold["validacao_ids"])
        if treino & validacao or treino | validacao != universo:
            raise ValueError("Treino e validação não particionam o universo.")
        for grupo in grupos:
            ids = set(grupo["ids"])
            if sum(bool(ids & bloco) for bloco in (treino, validacao, membros - universo)) > 1:
                raise ValueError("Grupo de duplicatas atravessa o corte.")
        cobertura.update(validacao)
    if cobertura != Counter({i: 1 for i in universo}):
        raise ValueError("Cada questão deve ter exatamente uma validação.")


def criar_internas(treino_ids: list, grupos: list, indice_externo: int, config_nested: dict) -> list:
    universo = _ids(treino_ids)
    quantidade = config_nested["particoes_internas"]
    if type(quantidade) is not int or quantidade < 2:
        raise ValueError("Número de partições internas inválido.")
    selecionados = []
    for grupo in grupos:
        ids = set(grupo["ids"])
        if ids & universo:
            if not ids <= universo:
                raise ValueError("Um grupo cruza o treino externo.")
            selecionados.append(sorted(ids))
    salt = config_nested["salt"]
    selecionados.sort(key=lambda ids: (hashlib.sha256(
        _json([salt, indice_externo, ids])).hexdigest(), ids))
    baldes = [[] for _ in range(quantidade)]
    for ids in selecionados:
        destino = min(range(quantidade), key=lambda i: (len(baldes[i]), i))
        baldes[destino].extend(ids)
    folds = [{"indice": i, "treino_ids": sorted(universo - set(b)),
              "validacao_ids": sorted(b)} for i, b in enumerate(baldes)]
    validar_particoes(folds, universo, grupos)
    return folds


def selecionar(resultados: dict, receitas: dict) -> str:
    if not receitas or set(resultados) != set(receitas):
        raise ValueError("Resultados devem cobrir exatamente as receitas.")
    coberturas = []
    for ps in resultados.values():
        coberturas.append(_ids([p["id"] for p in ps]))
        if any(type(p["acertos"][m]) is not bool for p in ps for m in ("ramo", "exato")):
            raise ValueError("Acertos devem ser booleanos.")
    if any(ids != coberturas[0] for ids in coberturas):
        raise ValueError("Receitas comparadas em questões diferentes.")
    return min(receitas, key=lambda n: (
        -sum(p["acertos"]["ramo"] for p in resultados[n]),
        -sum(p["acertos"]["exato"] for p in resultados[n]),
        receitas[n]["prioridade"], n,
    ))


def comparar_pareado(baseline: list, predicoes: list) -> dict:
    if _ids([p["id"] for p in baseline]) != _ids([p["id"] for p in predicoes]):
        raise ValueError("A comparação pareada exige exatamente os mesmos IDs.")
    bs = {p["id"]: p for p in baseline}
    saida = {}
    for modo in ("ramo", "imediato", "exato"):
        transicoes = Counter((bs[p["id"]]["acertos"][modo], p["acertos"][modo]) for p in predicoes)
        saida[modo] = {"melhorou": transicoes[(False, True)],
                       "piorou": transicoes[(True, False)],
                       "ambos_corretos": transicoes[(True, True)],
                       "ambos_errados": transicoes[(False, False)],
                       "ganho_liquido": transicoes[(False, True)] - transicoes[(True, False)]}
    return saida


def _resumo(ps, taxonomia):
    por_id = taxonomia["por_id"]
    return {**resumir(ps),
            "niveis_sugeridos": dict(sorted(Counter(por_id[p["tema_sugerido_id"]]["nivel"] for p in ps).items())),
            "folhas_ativas_sugeridas": sum(not any(
                t["status"] == "active" and p["tema_sugerido_id"] in t["ancestrais_ids"]
                for t in por_id.values()) for p in ps)}


def _parametros_baseline():
    return {"modo": "hibrido", "peso_exemplos": 0.0, "peso_leis": 0.0,
            "vizinhos": "lexicais", "rrf_k": 20, "peso_semantico": 0.5,
            "lexical": {"peso_catalogo": 0.7, "peso_exemplos": 0.3, "peso_leis": 0.0}}


def _predizer_corte(qs, rs_treino, taxonomia, cache, treino, validacao, receitas):
    # Só os rótulos de treino cruzam a interface do classificador.
    qs_treino = [qs[i] for i in sorted(treino)]
    rotulos = [rs_treino[i] for i in sorted(treino)]
    motor = Motor(qs_treino, rotulos, taxonomia, cache) if any(
        r["parametros"]["modo"] != "baseline_m3" for r in receitas.values()) else None
    baseline = treinar(qs_treino, rotulos, taxonomia, _parametros_baseline(), cache) if any(
        r["parametros"]["modo"] == "baseline_m3" for r in receitas.values()) else None
    resultado = {nome: [] for nome in receitas}
    for i in sorted(validacao):
        for nome, receita in sorted(receitas.items()):
            p = (predizer(baseline, qs[i], cache, top_k=5)
                 if receita["parametros"]["modo"] == "baseline_m3"
                 else motor.predizer(qs[i], receita["parametros"], top_k=5))
            resultado[nome].append({**p, "receita": nome})
    return resultado


def _avaliar_corte(predicoes, rs, taxonomia, treino, indice):
    vistos = {rs[i]["tema_central_id"] for i in treino if not rs[i]["fora_da_taxonomia"]}
    return {nome: [{**avaliar_predicao(p, rs[p["id"]], taxonomia, vistos),
                    "particao_interna": indice} for p in ps]
            for nome, ps in predicoes.items()}


def _oof(qs, rs, taxonomia, cache, folds, receitas):
    resultado = {nome: [] for nome in receitas}
    for f in folds:
        treino, validacao = f["treino_ids"], f["validacao_ids"]
        ps = _predizer_corte(qs, {i: rs[i] for i in treino}, taxonomia, cache,
                             treino, validacao, receitas)
        avaliadas = _avaliar_corte(ps, rs, taxonomia, treino, f["indice"])
        for nome in receitas:
            resultado[nome].extend(avaliadas[nome])
    return {nome: sorted(ps, key=lambda p: p["id"]) for nome, ps in resultado.items()}


def conferir_baseline(reproduzida, congelada):
    if _ids([p["id"] for p in reproduzida]) != _ids([p["id"] for p in congelada]):
        raise ValueError("Baseline não cobre as mesmas80 questões.")
    anteriores = {p["id"]: p for p in congelada}
    for p in reproduzida:
        a = anteriores[p["id"]]
        if any(p[c] != a[c] for c in ("tema_sugerido_id", "score", "margem", "acertos", "acerto_top_k_ramo")):
            raise ValueError("Baseline M3 não reproduzida exatamente.")
        if [(t["tema_id"], t["score"]) for t in p["top_candidatos"]] != [
                (t["tema_id"], t["score"]) for t in a["top_candidatos"]]:
            raise ValueError("Top5 da baseline divergente.")


def processar_desenvolvimento(questoes, rotulos_dev, taxonomia, protocolo, grupos,
                             config, cache, baseline_congelada, progresso=None):
    dev = _ids(protocolo["desenvolvimento_ids"])
    if (_ids([q["id"] for q in questoes]) != dev
            or _ids([r["id"] for r in rotulos_dev]) != dev
            or set(cache["questoes"]) != dev):
        raise ValueError("Desenvolvimento recebe somente questões, rótulos e vetores dev.")
    if (config["criterio_selecao"] != CRITERIO or config["top_k"] != 5
            or config["publicacao_automatica"] is not False
            or config["recalibrar"] is not False or config["promover_entrega_m5"] is not False):
        raise ValueError("Protocolo não corresponde ao experimento de ranking.")
    receitas = config["receitas"]
    if "baseline_m3" not in receitas or len({r["prioridade"] for r in receitas.values()}) != len(receitas):
        raise ValueError("Baseline ou prioridades inválidas.")
    qs, rs = {q["id"]: q for q in questoes}, {r["id"]: r for r in rotulos_dev}
    folds = protocolo["particoes_internas"]
    validar_particoes(folds, dev, grupos)
    resultados = _oof(qs, rs, taxonomia, cache, folds, receitas)
    conferir_baseline(resultados["baseline_m3"], baseline_congelada)
    selecionada = selecionar(resultados, receitas)
    if progresso:
        progresso("OOF concluído; baseline M3 idêntica; iniciando avaliação aninhada.")
    nested, escolhas, particoes = [], [], []
    for externo in folds:
        treino = externo["treino_ids"]
        internas = criar_internas(treino, grupos, externo["indice"], config["nested"])
        # Nem questões nem rótulos da validação externa chegam à seleção interna.
        qs_in = {i: qs[i] for i in treino}
        rs_in = {i: rs[i] for i in treino}
        cache_in = {**cache, "questoes": {i: cache["questoes"][i] for i in treino}}
        ensaio = _oof(qs_in, rs_in, taxonomia, cache_in, internas, receitas)
        nome = selecionar(ensaio, receitas)
        ps = _predizer_corte(qs, rs_in, taxonomia, cache, treino,
                             externo["validacao_ids"], {nome: receitas[nome]})
        avaliada = _avaliar_corte(ps, rs, taxonomia, treino, externo["indice"])[nome]
        nested.extend(avaliada)
        escolhas.append({"indice_externo": externo["indice"], "receita": nome,
                         "metricas_internas": {n: _resumo(p, taxonomia) for n, p in ensaio.items()},
                         "validacao_externa": _resumo(avaliada, taxonomia)})
        particoes.append({"externa": externo, "internas": internas})
        if progresso:
            progresso(f"Avaliação aninhada: partição externa {externo['indice']} concluída.")
    nested.sort(key=lambda p: p["id"])
    relatorio = {
        "schema": "desenvolvimento_refinamento_m6_v1",
        "natureza": config["natureza"], "receita_selecionada": selecionada,
        "baseline_m3_reproduzida_exatamente": True,
        "receitas_oof_selecao": {nome: _resumo(ps, taxonomia) for nome, ps in resultados.items()},
        "pareado_oof_selecao": comparar_pareado(resultados["baseline_m3"], resultados[selecionada]),
        "nested": {"natureza": "Processo de seleção das8 receitas dentro de cada treino externo; dados historicamente reutilizados, sem independência de toda a pesquisa.",
                   "geral": _resumo(nested, taxonomia), "particoes": escolhas,
                   "pareado_baseline": comparar_pareado(resultados["baseline_m3"], nested)},
        "calibracao_nova": False, "politica_publicacao_alterada": False,
    }
    produtos = {
        "metricas_desenvolvimento.json": _json(relatorio),
        "predicoes_oof.jsonl": _jsonl([p for n in sorted(resultados) for p in resultados[n]]),
        "predicoes_nested.jsonl": _jsonl(nested),
        "particoes_nested.json": _json(particoes),
        "receita_selecionada.json": _json({"schema": "receita_refinamento_m6_v1",
            "receita": selecionada, "parametros": receitas[selecionada]["parametros"],
            "treino_selecao_ids": sorted(dev), "selecionada_sem_resultado_reserva_m6": True,
            "sem_teste_independente": True, "score_e_probabilidade": False}),
    }
    return produtos, {"receita_selecionada": selecionada,
                      "oof": relatorio["receitas_oof_selecao"][selecionada],
                      "nested": relatorio["nested"]["geral"]}


def construir_produtos(raiz: Path, progresso=None):
    raiz = raiz.resolve()
    fixadas = ler_json(raiz, "config/modulo6/fontes.json")["sha256"]
    conferir_assinaturas(raiz, fixadas)
    implementacao = assinar(raiz, [
        p.relative_to(raiz).as_posix() for p in sorted((raiz / "classificacao_refinamento").glob("*.py"))
    ] + ["config/modulo6/fontes.json"])
    from classificacao_decisao.execucao import _carregar
    contexto = _carregar(raiz)
    protocolo, cache, taxonomia = contexto["protocolo"], contexto["cache"], contexto["taxonomia"]
    config = ler_json(raiz, "config/modulo6/protocolo.json")
    grupos = ler_json(raiz, "artefatos/preparacao/particoes.json")["grupos"]
    qs = {q["id"]: q for q in contexto["questoes"]}
    rotulos = ler_jsonl(raiz, "artefatos/preparacao/rotulos_referencia.jsonl")
    rs = {r["id"]: r for r in rotulos}
    dev, reserva, avaliacao = [set(protocolo[c]) for c in
        ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids")]
    if (len(rs) != len(rotulos) or set(rs) != dev | reserva
            or dev & reserva or (dev | reserva) & avaliacao or set(qs) != dev | reserva | avaliacao):
        raise ValueError("Universos oficiais divergentes.")
    baseline = [p for p in ler_jsonl(raiz, "artefatos/melhorias-v1/predicoes_desenvolvimento.jsonl")
                if p["receita"] == "hibrido_catalogo"]
    produtos, resumo = processar_desenvolvimento(
        [qs[i] for i in sorted(dev)], [rs[i] for i in sorted(dev)], taxonomia,
        protocolo, grupos, config, {**cache, "questoes": {i: cache["questoes"][i] for i in dev}},
        baseline, progresso)
    nome = resumo["receita_selecionada"]
    receita = {nome: config["receitas"][nome]}
    # Somente agora a receita escolhida gera o diagnóstico das20 conhecidas.
    ps = _predizer_corte(qs, {i: rs[i] for i in dev}, taxonomia, cache, dev, reserva, receita)
    diagnostico = _avaliar_corte(ps, rs, taxonomia, dev, -1)[nome]
    baseline_reserva = ler_jsonl(raiz, "artefatos/reserva-v1/predicoes_reserva.jsonl")
    metricas_reserva = {"schema": "diagnostico_reserva_conhecida_m6_v1",
        "natureza": config["reserva"], "usada_para_selecionar_receita": False,
        "teste_independente": False, "geral": _resumo(diagnostico, taxonomia),
        "pareado_baseline": comparar_pareado(baseline_reserva, diagnostico)}
    produtos["diagnostico_reserva_conhecida.json"] = _json(metricas_reserva)
    produtos["predicoes_reserva_conhecida.jsonl"] = _jsonl(diagnostico)
    if progresso:
        progresso("Diagnóstico pós-seleção concluído; gerando sugestões experimentais para559.")
    sugestoes = _predizer_corte(qs, rs, taxonomia, cache, dev | reserva, avaliacao, receita)[nome]
    produtos["sugestoes_avaliacao.jsonl"] = _jsonl([
        {**p, "uso": "sugestao_experimental_para_revisao", "score_e_probabilidade": False}
        for p in sugestoes])
    # O estado ajustado é reconstituído por receita + IDs + fontes/cache assinados;
    # os vetores TF-IDF não são duplicados em outro arquivo de vários megabytes.
    produtos["modelo_reconstruivel.json"] = _json({
        "schema": "modelo_refinamento_reconstruivel_v1", "receita": nome,
        "parametros": receita[nome]["parametros"], "treino_ids": sorted(dev | reserva),
        "fontes_sha256": fixadas, "implementacao_sha256": implementacao,
        "requer_encoder_ou_rede": False, "reajuste100_tem_teste_independente": False})
    resumo["reserva_conhecida"] = metricas_reserva["geral"]
    resumo["sugestoes_experimentais"] = len(sugestoes)
    conferir_assinaturas(raiz, fixadas)
    conferir_assinaturas(raiz, implementacao)
    produtos["manifesto.json"] = _json({
        "schema": "manifesto_refinamento_m6_v1", "fontes_sha256": fixadas,
        "implementacao_sha256": implementacao,
        "produtos_sha256": {n: hashlib.sha256(b).hexdigest() for n, b in produtos.items()},
        "modelo_linguagem_decide_tema": False, "chamadas_api": 0,
        "entrega_m5_preservada": True, "resumo": resumo})
    return produtos, resumo


def executar(raiz: Path, verificar=False, progresso=None):
    saida = _validar_saida(raiz, raiz / SAIDA)
    produtos, resumo = construir_produtos(raiz, progresso)
    if verificar:
        _conferir_existentes(saida, produtos, exigir_completo=True)
    else:
        publicar_produtos(saida, produtos)
    return resumo
