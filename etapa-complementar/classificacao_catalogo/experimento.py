"""Experimento M7 reexecutável, sem rede ou encoder durante a classificação."""

from collections import Counter
import hashlib
from pathlib import Path

from classificacao_decisao.execucao import _carregar
from classificacao_experimentos.contexto import assinar, conferir_assinaturas, ler_json, ler_jsonl
from classificacao_experimentos.entradas import construir_registros, validar_cache
from classificacao_experimentos.experimento import avaliar_predicao
from classificacao_local.experimento import resumir
from classificacao_refinamento.experimento import criar_internas, validar_particoes, comparar_pareado
from classificacao_topicos.pipeline import _json, _jsonl
from .catalogo import ARQUIVOS, carregar
from .motor import Representacao, RECEITAS
from .selecao import selecionar, aplicar, medir

PASTA_CACHE = "artefatos/catalogo-m7-embeddings"
SAIDA = "artefatos/catalogo-m7-v1"
PROTOCOLO_SHA256 = "77448049ed4c668ed550735530df81e4cfaa584d2121181d81415e2bd30c0ea1"


def _resumo(ps):
    return {**resumir(ps), "recuos_hierarquicos": sum(p.get("recuou_na_hierarquia", False) for p in ps),
            "niveis_sugeridos": dict(sorted(Counter(str(p.get("nivel_sugerido")) for p in ps).items()))}


def _corte(representacao, qs, rotulos_treino, treino, validacao, receitas):
    if set(treino) & set(validacao) or set(rotulos_treino) != set(treino):
        raise ValueError("Sobreposição ou rótulo de avaliação entrando no ajuste.")
    modelo = representacao.treinar([qs[i] for i in sorted(treino)],
                                  [rotulos_treino[i] for i in sorted(treino)])
    return {nome: [representacao.predizer(qs[i], modelo, nome) for i in sorted(validacao)]
            for nome in receitas}, modelo


def _oof(representacao, qs, rs_dev, folds, receitas):
    resultados = {nome: [] for nome in receitas}
    for f in folds:
        treino, validacao = f["treino_ids"], f["validacao_ids"]
        rs_treino = {i: rs_dev[i] for i in treino}
        ps, _ = _corte(representacao, qs, rs_treino, treino, validacao, receitas)
        vistos = {r["tema_central_id"] for r in rs_treino.values() if not r["fora_da_taxonomia"]}
        for nome in receitas:
            resultados[nome].extend({**avaliar_predicao(p, rs_dev[p["id"]], representacao.taxonomia, vistos),
                                     "particao": f["indice"]} for p in ps[nome])
    return {n: sorted(ps, key=lambda p: p["id"]) for n, ps in resultados.items()}


def construir_produtos(raiz: Path, progresso=print):
    raiz = raiz.resolve()
    contexto = _carregar(raiz)
    for modulo in (5, 6):
        checkpoint = ler_json(raiz, f"artefatos/checkpoints/modulo{modulo}.json")
        conferir_assinaturas(raiz, checkpoint["artefatos_sha256"])
    if hashlib.sha256((raiz / "config/modulo7/protocolo.json").read_bytes()).hexdigest() != PROTOCOLO_SHA256:
        raise ValueError("Protocolo alterado: esta implementação executa somente a grade M7 pré-registrada.")
    config = ler_json(raiz, "config/modulo7/protocolo.json")
    if config["receitas"] != list(RECEITAS):
        raise ValueError("Receitas divergem do protocolo pré-registrado.")
    taxonomia = carregar(raiz, contexto["taxonomia"])
    manifesto_cache = ler_json(raiz, f"{PASTA_CACHE}/manifesto.json")
    conferir_assinaturas(raiz, manifesto_cache["fontes_sha256"])
    conferir_assinaturas(raiz, {f"{PASTA_CACHE}/{n}": h for n, h in manifesto_cache["produtos_sha256"].items()})
    cache_novo = ler_json(raiz, f"{PASTA_CACHE}/vetores.json")
    validar_cache(cache_novo, construir_registros([], taxonomia["registros"], set()))
    fontes = assinar(raiz, ARQUIVOS + [
        "config/modulo7/protocolo.json", "config/modulo7/preparacao_catalogo.json",
        f"{PASTA_CACHE}/manifesto.json", f"{PASTA_CACHE}/vetores.json",
        "artefatos/preparacao/rotulos_referencia.jsonl", "artefatos/preparacao/particoes.json",
        "artefatos/embeddings-e5-m4-v1/vetores.json", "artefatos/embeddings-e5-m4-v1/manifesto.json",
        "artefatos/checkpoints/modulo5.json", "artefatos/checkpoints/modulo6.json",
        "classificacao_catalogo/.gitattributes", "classificacao_refinamento/experimento.py",
        "classificacao_local/lexical.py", "classificacao_local/classificador.py",
        "classificacao_experimentos/experimento.py", "classificacao_experimentos/entradas.py",
        "classificacao_topicos/avaliacao.py", "classificacao_topicos/pipeline.py",
        "artefatos/melhorias-v1/predicoes_desenvolvimento.jsonl", "artefatos/reserva-v1/predicoes_reserva.jsonl"
    ] + [p.relative_to(raiz).as_posix() for p in sorted((raiz / "classificacao_catalogo").glob("*.py"))])
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
    # Representação IDF só catálogo; o desenvolvimento não recebe vetores das20/559.
    motor_dev = Representacao(taxonomia, {**contexto["cache"], "questoes": {
        i: contexto["cache"]["questoes"][i] for i in dev}}, cache_novo)
    qs_dev, rs_dev = {i: qs[i] for i in dev}, {i: rs[i] for i in dev}
    progresso("M7: calculando previsões fora do treino nas80 referências de desenvolvimento.")
    resultados = _oof(motor_dev, qs_dev, rs_dev, folds, RECEITAS)
    politica_dev = selecionar(resultados, list(RECEITAS))
    aninhadas, selecoes, particoes = [], [], []
    for f in folds:
        treino = f["treino_ids"]
        internas = criar_internas(treino, grupos, f["indice"], config["validacao"]["interna"])
        progresso(f"M7: seleção interna do bloco externo {f['indice']}.")
        internas_ps = _oof(motor_dev, {i: qs_dev[i] for i in treino}, {i: rs_dev[i] for i in treino}, internas, RECEITAS)
        politica = selecionar(internas_ps, list(RECEITAS))
        externas = [p for p in resultados[politica["receita"]] if p["id"] in set(f["validacao_ids"])]
        aninhadas.extend({**p, "publicaria": aplicar(p, politica),
                         "probabilidade_condicional_grupo": politica["probabilidade_condicional"]} for p in externas)
        selecoes.append({"particao": f["indice"], "politica": politica,
                         "resultado_externo": medir(externas, [aplicar(p, politica) for p in externas])})
        particoes.append({"externa": f, "internas": internas})
    aninhadas.sort(key=lambda p: p["id"])
    medicao_aninhada = medir(aninhadas, [p["publicaria"] for p in aninhadas])
    passou = (medicao_aninhada["n"] >= 10 and medicao_aninhada["precision"] >= .95)
    politica_final = {**politica_dev, "habilitada": politica_dev["habilitada"] and passou,
                      "passou_validacao_aninhada": passou,
                      "garantia_populacional_95": False,
                      "probabilidade_e_do_grupo_na_selecao": True}
    baseline = [p for p in ler_jsonl(raiz, "artefatos/melhorias-v1/predicoes_desenvolvimento.jsonl")
                if p["receita"] == "hibrido_catalogo"]
    nome = politica_dev["receita"]
    resumo = {"schema": "experimento_catalogo_m7_v1", "receita_selecionada": nome,
               "metricas_receitas": {n: _resumo(ps) for n, ps in resultados.items()},
               "pareado_baseline_selecionada": comparar_pareado(baseline, resultados[nome]),
               "selecao_aninhada": {"geral": _resumo(aninhadas), "publicacao": medicao_aninhada,
                                    "particoes": selecoes},
               "politica_selecionada_dev": politica_dev,
               "politica_candidata_final": politica_final,
               "desenvolvimento_adaptativo": True,
               "limitacao": "80 reutilizadas em M2-M7; validação aninhada controla seleção desta grade, não apaga adaptação histórica.20 também conhecidas; não há novo teste independente.",
               "exportacao_oficial_m5_alterada": False}
    progresso("M7: seleção encerrada; diagnóstico exploratório nas20 já conhecidas.")
    motor = Representacao(taxonomia, contexto["cache"], cache_novo)
    # Reaproveitar somente atributos imutáveis calculados sem rótulos.
    motor.consultas.update(motor_dev.consultas)
    ps_reserva, modelo80 = _corte(motor, qs, rs_dev, dev, reserva, [nome])
    vistos = {r["tema_central_id"] for r in rs_dev.values() if not r["fora_da_taxonomia"]}
    reserva_avaliada = [avaliar_predicao(p, rs[p["id"]], taxonomia, vistos) for p in ps_reserva[nome]]
    resumo_reserva = {"teste_independente": False, "usada_para_selecao": False,
                      "geral": _resumo(reserva_avaliada),
                      "publicacao": medir(reserva_avaliada, [aplicar(p, politica_final) for p in reserva_avaliada]),
                      "pareado_baseline": comparar_pareado(ler_jsonl(raiz, "artefatos/reserva-v1/predicoes_reserva.jsonl"), reserva_avaliada)}
    progresso("M7: gerando559 sugestões experimentais com ajuste nas100 referências humanas.")
    ps_avaliacao, modelo100 = _corte(motor, qs, rs, dev | reserva, avaliacao, [nome])
    sugestoes = [{**p, "publicaria_politica_candidata": aplicar(p, politica_final),
                 "uso": "experimento_separado_nao_substitui_entrega_m5", "score_e_probabilidade": False}
                for p in ps_avaliacao[nome]]
    resumo["avaliacao559"] = {"total": len(sugestoes),
                                "publicaria": sum(p["publicaria_politica_candidata"] for p in sugestoes),
                                "precisao_observada": None, "motivo": "Sem rótulos humanos oficiais disponíveis."}
    produtos = {"metricas.json": _json(resumo), "politica.json": _json(politica_final),
                 "predicoes_desenvolvimento.jsonl": _jsonl([p for n in RECEITAS for p in resultados[n]]),
                 "predicoes_aninhadas.jsonl": _jsonl(aninhadas), "particoes_aninhadas.json": _json(particoes),
                 "diagnostico_reserva_conhecida.json": _json(resumo_reserva),
                 "predicoes_reserva_conhecida.jsonl": _json(reserva_avaliada),
                 "sugestoes_avaliacao.jsonl": _jsonl(sugestoes),
                 "modelo80.json": _json(modelo80), "modelo100.json": _json(modelo100)}
    conferir_assinaturas(raiz, fontes)
    produtos["manifesto.json"] = _json({"schema": "manifesto_catalogo_m7_v1",
        "entradas_implementacao_sha256": fontes,
        "produtos_sha256": {n: hashlib.sha256(b).hexdigest() for n, b in produtos.items()},
        "llm_na_decisao": False, "encoder_na_decisao": False, "chamadas_api": 0})
    return produtos, resumo, resumo_reserva


def executar(raiz: Path, verificar=False):
    produtos, resumo, reserva = construir_produtos(raiz, lambda s: print(s, flush=True))
    destino = raiz / SAIDA
    if verificar:
        if not destino.is_dir() or {p.name for p in destino.iterdir()} != set(produtos):
            raise ValueError("Pacote M7 ausente ou contém arquivos inesperados.")
        for n, b in produtos.items():
            if (destino / n).read_bytes() != b:
                raise ValueError("Reprodução divergente: " + n)
        print("Reprodução M7: todos os11 arquivos idênticos byte a byte.", flush=True)
    else:
        destino.mkdir(parents=True, exist_ok=True)
        if any((destino/n).exists() and (destino/n).read_bytes() != b for n, b in produtos.items()):
            raise ValueError("Artefato existente divergente; crie outra versão.")
        for n, b in produtos.items():
            (destino/n).write_bytes(b)
    print(_json({"receita": resumo["receita_selecionada"],
                 "receitas": resumo["metricas_receitas"],
                 "aninhada": resumo["selecao_aninhada"]["publicacao"],
                 "reserva_conhecida": reserva["geral"], "avaliacao559": resumo["avaliacao559"]}).decode(), flush=True)
