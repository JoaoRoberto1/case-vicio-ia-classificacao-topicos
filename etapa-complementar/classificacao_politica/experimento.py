"""Seleção aninhada de seis filtros; comparação diagnóstica sem mudar o ranking."""

from pathlib import Path

from classificacao_decisao.calibracao import metricas as calibracao
from classificacao_decisao.entrega import gerar_csv, validar_csv
from classificacao_experimentos.contexto import assinar, conferir_assinaturas, ler_json, ler_jsonl
from classificacao_precisao.confianca import ajustar, prever
from classificacao_topicos.pipeline import _json, _jsonl
from .politica import ANCORA, RECEITAS_CONCORDANCIA, preparar, selecionar, aplicar, curvas, resumir
from .preparacao import CACHE, M8, PROTOCOLO, carregar_cache, salvar, sha

SAIDA = "artefatos/politica-m9-v1"


def avaliar_bloco(internas, externas):
    """Alvos externos só são utilizados depois de congelar escolha e confiança."""
    ids_treino = {p["id"] for p in internas}
    ids_teste = {p["id"] for p in externas}
    if not ids_treino or not ids_teste or ids_treino & ids_teste:
        raise ValueError("Bloco externo sobreposto ao ajuste da política.")
    politica = selecionar(internas)
    modelo = ajustar(internas)
    previsoes = [{**p, "confianca": prever(modelo, p)} for p in externas]
    previsoes = [{**p, "publicaria_m9": aplicar(p, politica)} for p in previsoes]
    return politica, modelo, previsoes


def avaliar_estabilidade(resumo):
    """Regra operacional registrada; não equivale a garantia populacional."""
    blocos = resumo["por_particao"]
    motivos = []
    if resumo["n"] == 0 or resumo["precision"] < .95:
        motivos.append("Precisão externa agregada de 95% não observada.")
    if len(blocos) != 3 or any(b["n"] == 0 for b in blocos):
        motivos.append("Publicações não se repetiram nos três blocos externos.")
    if any(b["n"] > 0 and b["precision"] < .95 for b in blocos):
        motivos.append("Há bloco com publicações e precisão observada abaixo de 95%.")
    return {"aprovada_experimentalmente": not motivos, "motivos": motivos,
            "garantia_populacional_95": False,
            "limitacao": "Mesmo 1/1 em cada bloco passa; suporte e Wilson devem ser lidos. Não é teste novo independente."}


def _ler_resultados(raiz):
    ps = ler_jsonl(raiz, f"{M8}/predicoes_desenvolvimento.jsonl")
    return {n: [p for p in ps if p["receita"] == n] for n in RECEITAS_CONCORDANCIA}


def _cobertura_sem_rotulos(ps, politica):
    n = sum(aplicar(p, politica) for p in ps)
    return {"total": len(ps), "n": n, "coverage": n / len(ps),
            "precision": None, "motivo": "Sem rótulos humanos disponíveis."}


def construir_produtos(raiz):
    raiz = raiz.resolve()
    cache = carregar_cache(raiz)
    nomes = [PROTOCOLO, f"{CACHE}/manifesto.json", f"{M8}/manifesto.json", f"{M8}/metricas.json",
             f"{M8}/predicoes_desenvolvimento.jsonl", "artefatos/preparacao/temas_preparados.json",
             "classificacao_decisao/entrega.py", "classificacao_decisao/calibracao.py",
             "classificacao_catalogo/selecao.py", "scripts/revisar_politica.py"]
    nomes += [f"{CACHE}/{n}" for n in cache["produtos_sha256"]]
    nomes += [p.relative_to(raiz).as_posix() for p in sorted((raiz / "classificacao_politica").glob("*.py"))]
    fontes = assinar(raiz, nomes)
    resultados = _ler_resultados(raiz)
    dev = preparar(resultados)
    if len(dev) != 80:
        raise ValueError("Desenvolvimento precisa conter 80 referências únicas.")
    # Escolha com OOF internas globais, antes de avaliar o procedimento externo
    # M9 ou consultar as coortes 20/559; não é uma nova reserva independente.
    politica_final = selecionar(dev)
    modelo_final = ajustar(dev)
    aninhadas, selecoes = [], []
    for indice in (1, 2, 3):
        bloco = ler_json(raiz, f"{CACHE}/internas_bloco{indice}.json")
        internas = preparar(bloco["predicoes"])
        treino = set(bloco["externa"]["treino_ids"])
        teste = set(bloco["externa"]["validacao_ids"])
        if treino & teste or treino | teste != {p["id"] for p in dev}:
            raise ValueError("Partição externa não cobre o desenvolvimento.")
        if {p["id"] for p in internas} != treino:
            raise ValueError("Cache interno contém IDs fora do treino externo.")
        externas = [p for p in dev if p["id"] in teste]
        if {p["particao_interna"] for p in externas} != {indice}:
            raise ValueError("Partições do ranking externo e da preparação divergem.")
        politica, modelo, ps = avaliar_bloco(internas, externas)
        aninhadas.extend(ps)
        selecoes.append({"particao": indice, "politica": politica, "calibrador": modelo,
                         "resultado": resumir(ps, [p["publicaria_m9"] for p in ps])})
    aninhadas.sort(key=lambda p: p["id"])
    if len(aninhadas) != 80 or len({p["id"] for p in aninhadas}) != 80:
        raise ValueError("Avaliação externa precisa conter exatamente 80 IDs.")
    externa = resumir(aninhadas, [p["publicaria_m9"] for p in aninhadas])
    estabilidade = avaliar_estabilidade(externa)
    curvas_externas = curvas(aninhadas, "confianca")
    # A reserva conhecida e a avaliação sem rótulos nunca voltam à seleção.
    ps20 = ler_jsonl(raiz, f"{CACHE}/predicoes_20_concordancia.jsonl")
    ps559 = ler_jsonl(raiz, f"{CACHE}/sugestoes_559_concordancia.jsonl")
    for ps in (ps20, ps559):
        for p in ps:
            p["confianca"] = prever(modelo_final, p)
            p["publicaria_m9"] = aplicar(p, politica_final)
    conjuntos = [{p["id"] for p in ps} for ps in (aninhadas, ps20, ps559)]
    if [len(c) for c in conjuntos] != [80, 20, 559] or len(set.union(*conjuntos)) != 659:
        raise ValueError("Universos 80/20/559 incompletos ou sobrepostos.")
    cobertura559 = _cobertura_sem_rotulos(ps559, politica_final)
    diagnostico20 = resumir(ps20, [p["publicaria_m9"] for p in ps20])
    curvas559 = []
    for regra in curvas_externas:
        fixa = {**regra, "habilitada": True}
        curvas559.append({"regra": regra["regra"], **_cobertura_sem_rotulos(ps559, fixa)})
    metricas_m8 = ler_json(raiz, f"{M8}/metricas.json")
    resumo = {
        "schema": "revisao_politica_m9_v1", "receita_fixa": ANCORA,
        "natureza": "Exploratória; referências historicamente reutilizadas; sem teste novo independente.",
        "selecao_interna": politica_final,
        "procedimento_externo": externa, "estabilidade": estabilidade,
        "curvas_externas_diagnosticas": curvas_externas,
        "curvas_559_sem_rotulos": curvas559,
        "calibracao_externa": calibracao([p["confianca"] for p in aninhadas], [p["acertos"]["ramo"] for p in aninhadas]),
        "reserva20_diagnostico": {**diagnostico20, "teste_independente": False, "usada_na_selecao": False},
        "candidata559": cobertura559,
        "controle_m8": {"procedimento_externo": metricas_m8["selecao_aninhada"]["publicacao"],
                        "avaliacao559": metricas_m8["avaliacao559"]},
        "oficial_substituida": False,
        "limite_559": "Ranking reajustado com 100 referências e confiança com 80 OOF. Cobertura candidata não comprova precisão.",
    }
    registros = []
    for p in aninhadas + ps20 + ps559:
        registros.append({"id": p["id"], "decisao": "publicar" if p["publicaria_m9"] else "revisar",
                          "tema_central_id": p["tema_sugerido_id"], "extras_ids": "", "confianca": p["confianca"],
                          "motivo": "Simulação M9 exploratória; consultar métricas antes de qualquer publicação."})
    csv = gerar_csv(registros)
    temas = ler_json(raiz, "artefatos/preparacao/temas_preparados.json")
    resumo["contrato_csv_candidato"] = validar_csv(csv, set.union(*conjuntos), {"por_id": {t["tema_id"]: t for t in temas}})
    produtos = {"metricas.json": _json(resumo), "politica_candidata.json": _json(politica_final),
                "calibracao_e_selecoes.json": _json({"final": modelo_final, "externas": selecoes}),
                "predicoes_externas.jsonl": _jsonl(aninhadas), "predicoes_20.jsonl": _jsonl(ps20),
                "sugestoes_559.jsonl": _jsonl(ps559), "publicacao_candidata.csv": csv,
                "ANALISE.md": relatorio(resumo).encode("utf-8")}
    conferir_assinaturas(raiz, fontes)
    produtos["manifesto.json"] = _json({"schema": "manifesto_politica_m9_v1", "fontes_sha256": fontes,
                                         "produtos_sha256": {n: sha(b) for n, b in produtos.items()},
                                         "chamadas_API": 0, "encoder": False, "LLM_na_decisao": False})
    return produtos, resumo


def relatorio(m):
    def pct(x):
        return "indefinida" if x is None else f"{100*x:.2f}%".replace(".", ",")
    def intervalo(row):
        w = row["wilson95"]
        return "indefinido" if w is None else f"{pct(w['inferior'])} a {pct(w['superior'])}"
    p, e, c = m["selecao_interna"], m["procedimento_externo"], m["candidata559"]
    linhas = ["# Módulo 9 — revisão da política de publicação", "",
              "João Roberto de Oliveira Felix", "",
              "Experimento exploratório. O CSV desta pasta é uma simulação candidata, não substitui a entrega oficial.", "",
              f"Política interna: **{p['regra'] or 'abstenção'}**; {p['k']}/{p['n']} acertos internos. "
              "Ranking fixo `sinais_large`; nenhum tema foi escolhido ou validado por LLM.", "",
              f"Procedimento externo: **{e['k']}/{e['n']}**, precisão {pct(e['precision'])}, "
              f"cobertura {pct(e['coverage'])} nas 80 referências. Wilson de 95%: {intervalo(e)}.", "",
              f"Aplicação candidata: **{c['n']}/559 = {pct(c['coverage'])}**. Precisão nas 559 desconhecida.", "",
              f"Passou pelo critério operacional de estabilidade: **{'sim' if m['estabilidade']['aprovada_experimentalmente'] else 'não'}**."]
    linhas += ["", *[f"- {motivo}" for motivo in m["estabilidade"]["motivos"]], "",
               "## Estabilidade externa", "", "| Bloco | Acertos/aceitos | Cobertura | Precisão |", "|---|---:|---:|---:|"]
    linhas += [f"| {b['particao']} | {b['k']}/{b['n']} | {pct(b['coverage'])} | {pct(b['precision'])} |" for b in e["por_particao"]]
    linhas += ["", "## Seis filtros: diagnóstico, sem nova seleção", "",
               "| Filtro | Acertos/aceitos externos | Precisão externa | Cobertura externa | Aceitos nas 559 |",
               "|---|---:|---:|---:|---:|"]
    for r, a in zip(m["curvas_externas_diagnosticas"], m["curvas_559_sem_rotulos"]):
        linhas.append(f"| {r['regra']} | {r['k']}/{r['n']} | {pct(r['precision'])} | {pct(r['coverage'])} | {a['n']} |")
    r = m["reserva20_diagnostico"]
    linhas += ["", f"Diagnóstico nas 20 referências já conhecidas: {r['k']}/{r['n']} entre aceitas. "
               "Esse resultado foi calculado após a seleção e não é teste independente.", "",
               "## Interpretação", "",
               "O mínimo global de 10 foi removido deste experimento. A escolha entre seis filtros ocorre apenas nas previsões "
               "internas. Cada calibrador externo foi ajustado com rankings reconstituídos exclusivamente no treino daquele bloco. "
               "A confiança OOF global nunca é utilizada como confiança externa.", "",
               "A concordância exige o mesmo tema em sinais_small, large_rrf20 e sinais_large. Os algoritmos são correlacionados: "
               "concordar não equivale a validar. O filtro não altera o tema escolhido pela receita âncora.", "",
               "A estabilidade exige publicação nos três blocos e precisão observada ≥95% em cada um e no agregado. "
               "É uma escolha operacional, não garantia estatística; até 1/1 em cada bloco passaria. "
               "Wilson é descritivo, não corrige reutilização histórica/seleção adaptativa e não certifica as 559 questões.", "",
               "As curvas não são usadas para trocar retrospectivamente a política escolhida. As 100 referências já foram "
               "consultadas em rodadas anteriores, e as 300 questões recentes não têm rótulos humanos disponíveis. "
               "O experimento não cria um novo teste independente. Não ampliar a grade para procurar um resultado favorável.", "",
               "Reprodução: `python -E -X utf8 -B -S scripts/revisar_politica.py --verificar` na pasta `etapa-complementar`. "
               "O manifesto registra as fontes, o código e os produtos usados.", ""]
    return "\n".join(linhas)


def executar(raiz: Path, verificar=False):
    produtos, resumo = construir_produtos(raiz)
    for nome, conteudo in produtos.items():
        salvar(raiz / SAIDA, nome, conteudo, verificar)
    salvar(raiz / SAIDA, ".gitattributes", b"* -text\n", verificar)
    return {"pasta": SAIDA, "regra": resumo["selecao_interna"]["regra"],
            "externa": resumo["procedimento_externo"], "candidata559": resumo["candidata559"],
            "estabilidade": resumo["estabilidade"], "oficial_substituida": False}
