"""M8: comparação numérica, seleção aninhada e exportação sem encoder ou rede."""

import hashlib
from pathlib import Path

from classificacao_catalogo.catalogo import ARQUIVOS, carregar
from classificacao_catalogo.experimento import _resumo, PASTA_CACHE
from classificacao_decisao.execucao import _carregar
from classificacao_decisao.calibracao import metricas as metricas_calibracao
from classificacao_experimentos.contexto import assinar, conferir_assinaturas, ler_json, ler_jsonl
from classificacao_experimentos.entradas import construir_registros, validar_cache
from classificacao_experimentos.experimento import avaliar_predicao
from classificacao_refinamento.experimento import criar_internas, validar_particoes, comparar_pareado
from classificacao_topicos.pipeline import _json, _jsonl
from .motor import Motor, RECEITAS
from .confianca import ajustar, prever, selecionar, aplicar, medir

PROTOCOLO_SHA256 = "4ac9d655cf825b98bfc5b2151466e618637fd7d906deeaf0de6e3cd5730ba115"
CACHE_LARGE = "artefatos/embeddings-e5-large-m8"
SAIDA = "artefatos/precisao-m8-v1"
PARCIAL = "artefatos/precisao-m8-small-v1"


def _corte(motor, qs, rs, treino, validacao, receitas):
    if set(treino) & set(validacao) or set(rs) != set(treino):
        raise ValueError("Sobreposição ou rótulo de avaliação entrando no ajuste.")
    modelo = motor.treinar([qs[i] for i in sorted(treino)], [rs[i] for i in sorted(treino)], receitas)
    return {n: [motor.predizer(qs[i], modelo, n) for i in sorted(validacao)] for n in receitas}, modelo


def _oof(motor, qs, rs, folds, receitas):
    resultados = {n: [] for n in receitas}
    for f in folds:
        treino, validacao = f["treino_ids"], f["validacao_ids"]
        rs_treino = {i: rs[i] for i in treino}
        ps, _ = _corte(motor, qs, rs_treino, treino, validacao, receitas)
        vistos = {r["tema_central_id"] for r in rs_treino.values() if not r["fora_da_taxonomia"]}
        for n in receitas:
            resultados[n].extend({**avaliar_predicao(p, rs[p["id"]], motor.taxonomia, vistos),
                                   "particao_interna": f["indice"]} for p in ps[n])
    for n, ps in resultados.items():
        # Cross-fit do segundo estágio para seleção. As características OOF compartilham
        # treinos; a independência exigida para medir o procedimento é a externa completa.
        for particao in sorted({p["particao_interna"] for p in ps}):
            calibrador = ajustar([p for p in ps if p["particao_interna"] != particao])
            for p in ps:
                if p["particao_interna"] == particao:
                    p["confianca_oof"] = prever(calibrador, p)
        resultados[n] = sorted(ps, key=lambda p: p["id"])
    return resultados


def _calibracao(ps, campo):
    alvos = [p["acertos"]["ramo"] for p in ps]
    return metricas_calibracao([p[campo] for p in ps], alvos)


def _comparar_reserva_m7(raiz, predicoes):
    # O produtor M7 gravou um array JSON, apesar da extensão histórica .jsonl.
    baseline = ler_json(raiz, "artefatos/catalogo-m7-v1/predicoes_reserva_conhecida.jsonl")
    return comparar_pareado(baseline, predicoes)


def carregar_contexto(raiz, parcial):
    contexto = _carregar(raiz)
    for modulo in (5, 6, 7):
        conferir_assinaturas(raiz, ler_json(raiz, f"artefatos/checkpoints/modulo{modulo}.json")["artefatos_sha256"])
    if hashlib.sha256((raiz / "config/modulo8/protocolo.json").read_bytes()).hexdigest() != PROTOCOLO_SHA256:
        raise ValueError("Protocolo M8 diverge da versão registrada antes das métricas.")
    config = ler_json(raiz, "config/modulo8/protocolo.json")
    if config["receitas"] != list(RECEITAS):
        raise ValueError("Grade diverge do protocolo M8.")
    tax = carregar(raiz, contexto["taxonomia"])
    documentos = [ler_json(raiz, p) for p in ARQUIVOS]
    ancoras = ler_json(raiz, "config/modulo8/ancoras_normativas.json")
    manifesto = ler_json(raiz, f"{PASTA_CACHE}/manifesto.json")
    conferir_assinaturas(raiz, manifesto["fontes_sha256"])
    conferir_assinaturas(raiz, {f"{PASTA_CACHE}/{n}": h for n, h in manifesto["produtos_sha256"].items()})
    cache = ler_json(raiz, f"{PASTA_CACHE}/vetores.json")
    validar_cache(cache, construir_registros([], tax["registros"], set()))
    large = None
    if not parcial:
        manifesto_large = ler_json(raiz, f"{CACHE_LARGE}/manifesto.json")
        conferir_assinaturas(raiz, {f"{CACHE_LARGE}/{n}": h for n, h in manifesto_large["produtos_sha256"].items()})
        large = ler_json(raiz, f"{CACHE_LARGE}/vetores.json")
        validar_cache(large, construir_registros(contexto["questoes"], tax["registros"],
                                                {q["id"] for q in contexto["questoes"]}), dimensoes=1024)
        if manifesto_large["configuracao"] != ler_json(raiz, "config/modulo8/embeddings_large.json"):
            raise ValueError("Configuração do encoder diverge do cache preparado.")
    nomes = set(ARQUIVOS + [
        "config/modulo8/protocolo.json", "config/modulo8/ancoras_normativas.json",
        f"{PASTA_CACHE}/manifesto.json", f"{PASTA_CACHE}/vetores.json",
        "artefatos/preparacao/rotulos_referencia.jsonl", "artefatos/preparacao/particoes.json",
        "artefatos/embeddings-e5-m4-v1/vetores.json", "artefatos/embeddings-e5-m4-v1/manifesto.json",
        "artefatos/catalogo-m7-v1/predicoes_desenvolvimento.jsonl",
        "artefatos/catalogo-m7-v1/predicoes_reserva_conhecida.jsonl",
        "classificacao_precisao/.gitattributes", "classificacao_refinamento/experimento.py",
        "classificacao_decisao/calibracao.py"])
    for modulo in (5, 6, 7):
        nomes.add(f"artefatos/checkpoints/modulo{modulo}.json")
    for pasta in ("classificacao_catalogo", "classificacao_precisao"):
        nomes.update(p.relative_to(raiz).as_posix() for p in sorted((raiz / pasta).glob("*.py"))
                     if p.name not in {"preparar_large.py", "entrega.py"})
    if not parcial:
        nomes.update([f"{CACHE_LARGE}/manifesto.json", f"{CACHE_LARGE}/vetores.json",
                      "config/modulo8/embeddings_large.json"])
    return contexto, config, tax, documentos, ancoras, cache, large, assinar(raiz, sorted(nomes))


def construir_produtos(raiz: Path, parcial=False, progresso=print):
    raiz = raiz.resolve()
    contexto, config, tax, docs, ancoras, cache, large, fontes = carregar_contexto(raiz, parcial)
    protocolo = contexto["protocolo"]
    dev, reserva, avaliacao = [set(protocolo[c]) for c in ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids")]
    qs = {q["id"]: q for q in contexto["questoes"]}
    rs = {r["id"]: r for r in ler_jsonl(raiz, "artefatos/preparacao/rotulos_referencia.jsonl")}
    if (len(dev) != 80 or len(reserva) != 20 or len(avaliacao) != 559 or set(rs) != dev | reserva
            or dev & reserva or (dev | reserva) & avaliacao or set(qs) != dev | reserva | avaliacao):
        raise ValueError("Universos incompatíveis com o protocolo fixado.")
    grupos = ler_json(raiz, "artefatos/preparacao/particoes.json")["grupos"]
    folds = protocolo["particoes_internas"]
    validar_particoes(folds, dev, grupos)
    receitas = list(RECEITAS[:3] if parcial else RECEITAS)
    cache_dev = {**contexto["cache"], "questoes": {i: contexto["cache"]["questoes"][i] for i in dev}}
    large_dev = {**large, "questoes": {i: large["questoes"][i] for i in dev}} if large is not None else None
    motor = Motor(tax, cache_dev, cache, docs, large_dev, ancoras)
    qs_dev, rs_dev = {i: qs[i] for i in dev}, {i: rs[i] for i in dev}
    progresso("M8: ranking fora do treino e confiança nas80 referências de desenvolvimento.")
    resultados = _oof(motor, qs_dev, rs_dev, folds, receitas)
    baseline = [p for p in ler_jsonl(raiz, "artefatos/catalogo-m7-v1/predicoes_desenvolvimento.jsonl")
                if p["receita"] == "aprendido_hierarquico"]
    if len(baseline) != 80:
        raise ValueError("Baseline M7 incompleto.")
    for antigo, atual in zip(sorted(baseline, key=lambda p: p["id"]), resultados["baseline_m7"]):
        if any(antigo[k] != atual[k] for k in ("id", "tema_sugerido_id", "score", "margem", "acertos", "top_candidatos")):
            raise ValueError("Baseline M7 deixou de ser reproduzido exatamente.")
    politica_dev = selecionar(resultados, receitas)
    aninhadas, selecoes, particoes, calibradores_externos = [], [], [], []
    for f in folds:
        treino = f["treino_ids"]
        internas = criar_internas(treino, grupos, f["indice"], config["validacao"]["interna"])
        progresso(f"M8: seleção e calibração no treino do bloco externo{f['indice']}.")
        internas_ps = _oof(motor, {i: qs_dev[i] for i in treino}, {i: rs_dev[i] for i in treino}, internas, receitas)
        politica = selecionar(internas_ps, receitas)
        calibrador = ajustar(internas_ps[politica["receita"]])
        n = len(internas_ps[politica["receita"]])
        constante = (sum(p["acertos"]["ramo"] for p in internas_ps[politica["receita"]]) + .5)/(n+1)
        externas = [{**p, "confianca": prever(calibrador, p), "confianca_constante": constante}
                    for p in resultados[politica["receita"]] if p["id"] in set(f["validacao_ids"])]
        aninhadas.extend({**p, "publicaria": aplicar(p, politica)} for p in externas)
        selecoes.append({"particao": f["indice"], "politica": politica,
                         "resultado_externo": medir(externas, [aplicar(p, politica) for p in externas])})
        particoes.append({"externa": f, "internas": internas})
        calibradores_externos.append({"particao": f["indice"], "modelo": calibrador})
    aninhadas.sort(key=lambda p: p["id"])
    medicao = medir(aninhadas, [p["publicaria"] for p in aninhadas])
    passou = medicao["n"] >= 10 and medicao["precision"] >= .95
    politica_final = {**politica_dev, "habilitada": politica_dev["habilitada"] and passou,
                      "passou_validacao_aninhada": passou, "garantia_populacional_95": False}
    nome = politica_dev["receita"]
    resumo = {"schema": "experimento_precisao_m8_v1", "comparacao_parcial": parcial,
               "receita_selecionada": nome, "metricas_receitas": {n: _resumo(ps) for n, ps in resultados.items()},
               "calibracao_receitas_oof_interna": {n: _calibracao(ps, "confianca_oof") for n, ps in resultados.items()},
               "pareado_m7_selecionada": comparar_pareado(baseline, resultados[nome]),
               "selecao_aninhada": {"geral": _resumo(aninhadas), "publicacao": medicao, "particoes": selecoes,
                                    "calibracao": _calibracao(aninhadas, "confianca"),
                                    "calibracao_constante": _calibracao(aninhadas, "confianca_constante")},
               "politica_selecionada_dev": politica_dev, "politica_candidata_final": politica_final,
               "suporte_sinais_catalogo": motor.sinais.suporte_catalogo(),
               "desenvolvimento_adaptativo": True,
               "limitacao": "80 reutilizadas emM2–M8;20 também conhecidas. Não existe teste novo independente. A validação externa separa o ajuste desta grade, sem apagar a adaptação histórica. Cross-fit interno da confiança compartilha treinos dos rankers e serve apenas à seleção interna.",
               "encoder_na_decisao": False}
    calibrador = ajustar(resultados[nome])
    produtos = {"metricas.json": _json(resumo), "politica.json": _json(politica_final),
                "predicoes_desenvolvimento.jsonl": _jsonl([p for n in receitas for p in resultados[n]]),
                "predicoes_aninhadas.jsonl": _jsonl(aninhadas), "particoes_aninhadas.json": _json(particoes),
                "calibradores.json": _json({"externos": calibradores_externos, "final80OOF": calibrador})}
    if not parcial:
        progresso("M8: grade encerrada; diagnóstico nas20 conhecidas e refit100 para559 sugestões.")
        motor_final = Motor(tax, contexto["cache"], cache, docs, large, ancoras)
        motor_final._consultas.update(motor._consultas)
        motor_final.base.consultas.update(motor.base.consultas)
        ps_reserva, modelo80 = _corte(motor_final, qs, rs_dev, dev, reserva, [nome])
        vistos = {r["tema_central_id"] for r in rs_dev.values() if not r["fora_da_taxonomia"]}
        ps20 = [{**avaliar_predicao(p, rs[p["id"]], tax, vistos), "confianca": prever(calibrador, p)}
                for p in ps_reserva[nome]]
        ps20 = [{**p, "publicaria_politica_candidata": aplicar(p, politica_final)} for p in ps20]
        diagnostico = {"teste_independente": False, "usada_para_selecao": False, "geral": _resumo(ps20),
                      "publicacao": medir(ps20, [p["publicaria_politica_candidata"] for p in ps20]),
                      "calibracao": _calibracao(ps20, "confianca"),
                      "pareado_m7": _comparar_reserva_m7(raiz, ps20)}
        ps_avaliacao, modelo100 = _corte(motor_final, qs, rs, dev | reserva, avaliacao, [nome])
        ps559 = [{**p, "confianca": prever(calibrador, p)} for p in ps_avaliacao[nome]]
        ps559 = [{**p, "publicaria_politica_candidata": aplicar(p, politica_final)} for p in ps559]
        resumo["avaliacao559"] = {"total": 559, "publicaria": sum(p["publicaria_politica_candidata"] for p in ps559),
                                    "precisao_observada": None, "motivo": "Sem rótulos humanos oficiais disponíveis."}
        produtos.update({"metricas.json": _json(resumo), "modelo80.json": _json(modelo80), "modelo100.json": _json(modelo100),
                         "diagnostico_reserva_conhecida.json": _json(diagnostico),
                         "predicoes_reserva_conhecida.jsonl": _jsonl(ps20), "sugestoes_avaliacao.jsonl": _jsonl(ps559)})
    conferir_assinaturas(raiz, fontes)
    produtos["manifesto.json"] = _json({"schema": "manifesto_precisao_m8_v1", "entradas_implementacao_sha256": fontes,
        "produtos_sha256": {n: hashlib.sha256(b).hexdigest() for n, b in produtos.items()},
        "llm_na_decisao": False, "encoder_na_decisao": False, "chamadas_api": 0})
    return produtos, resumo


def executar(raiz: Path, verificar=False, parcial=False):
    produtos, resumo = construir_produtos(raiz, parcial, lambda s: print(s, flush=True))
    destino = raiz / (PARCIAL if parcial else SAIDA)
    if verificar:
        if not destino.is_dir() or {p.name for p in destino.iterdir()} != set(produtos):
            raise ValueError("Pacote M8 ausente ou com arquivos inesperados.")
        if any((destino/n).read_bytes() != b for n, b in produtos.items()):
            raise ValueError("Reprodução M8 divergente.")
        print("Reprodução M8: todos os produtos idênticos byte a byte.", flush=True)
    else:
        destino.mkdir(parents=True, exist_ok=True)
        if any((destino/n).exists() and (destino/n).read_bytes() != b for n, b in produtos.items()):
            raise ValueError("Artefato existente divergente; crie outra versão.")
        for n, b in produtos.items():
            (destino/n).write_bytes(b)
    print(_json({"receita": resumo["receita_selecionada"], "parcial": parcial,
                 "receitas": resumo["metricas_receitas"], "aninhada": resumo["selecao_aninhada"]["publicacao"],
                 "avaliacao559": resumo.get("avaliacao559")}).decode(), flush=True)
