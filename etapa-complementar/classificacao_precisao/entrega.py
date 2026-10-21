"""Entrega M8 em memória, preservando procedência e denominadores do case.

O CSV reutiliza o contrato M4. As 80 predições de seleção aninhada, 20 da
reserva já conhecida e 559 de avaliação são obrigatoriamente disjuntas.
Nenhum rótulo individual participa da exportação. A política final governa
todas as publicações; a decisão ``fora`` nunca é automatizada.
"""

import json
import math

from classificacao_decisao.calibracao import wilson
from classificacao_decisao.entrega import gerar_csv, validar_csv


_ORIGENS = (
    ("predicoes_aninhadas.jsonl", "selecao_aninhada", 80, "publicaria"),
    ("predicoes_reserva_conhecida.jsonl", "reserva_conhecida_modelo80", 20, "publicaria_politica_candidata"),
    ("sugestoes_avaliacao.jsonl", "avaliacao_modelo100", 559, "publicaria_politica_candidata"),
)
_QUANTIDADE = sum(n for _, _, n, _ in _ORIGENS)


def _constante_invalida(valor):
    raise ValueError(f"Constante JSON não finita: {valor}.")


def _texto(produtos, nome):
    conteudo = produtos.get(nome)
    if not isinstance(conteudo, bytes):
        raise ValueError(f"Produto {nome} ausente ou não fornecido em bytes.")
    try:
        return conteudo.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"Produto {nome} não é UTF-8 válido.") from None


def _ler_json(produtos, nome):
    try:
        resultado = json.loads(_texto(produtos, nome), parse_constant=_constante_invalida)
    except (json.JSONDecodeError, ValueError) as erro:
        raise ValueError(f"Produto {nome} inválido: {erro}") from None
    if not isinstance(resultado, dict):
        raise ValueError(f"Produto {nome} deve conter um objeto JSON.")
    return resultado


def _ler_jsonl(produtos, nome):
    registros = []
    for linha in _texto(produtos, nome).splitlines():
        if not linha.strip():
            continue
        try:
            registro = json.loads(linha, parse_constant=_constante_invalida)
        except (json.JSONDecodeError, ValueError) as erro:
            raise ValueError(f"Produto {nome} contém linha inválida: {erro}") from None
        if not isinstance(registro, dict):
            raise ValueError(f"Cada linha de {nome} deve ser um objeto JSON.")
        registros.append(registro)
    return registros


def _numero(valor, campo):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{campo} deve ser número finito entre zero e um.")
    try:
        valor = float(valor)
    except (OverflowError, ValueError):
        raise ValueError(f"{campo} fora do intervalo numérico.") from None
    if not math.isfinite(valor) or not 0 <= valor <= 1:
        raise ValueError(f"{campo} deve ser número finito entre zero e um.")
    return valor


def _publicacao_externa(metricas):
    aninhada = metricas.get("selecao_aninhada")
    if not isinstance(aninhada, dict) or not isinstance(aninhada.get("publicacao"), dict):
        raise ValueError("Métricas devem conter selecao_aninhada.publicacao.")
    externa = aninhada["publicacao"]
    if any(type(externa.get(c)) is not int for c in ("count", "n", "k")):
        raise ValueError("Contagens da seleção aninhada devem ser inteiras.")
    total, n, k = (externa[c] for c in ("count", "n", "k"))
    if total != 80 or not 0 <= k <= n <= total:
        raise ValueError("A avaliação externa deve representar as 80 referências de desenvolvimento.")
    cobertura = _numero(externa.get("coverage"), "coverage externa")
    if not math.isclose(cobertura, n / total, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("Cobertura externa incompatível com suas contagens.")
    precisao, intervalo = externa.get("precision"), externa.get("wilson95")
    esperado = wilson(k, n)
    if n == 0:
        if precisao is not None or intervalo is not None:
            raise ValueError("Sem publicações externas, precisão e intervalo devem ser null.")
    else:
        precisao = _numero(precisao, "precision externa")
        if not math.isclose(precisao, k / n, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("Precisão externa incompatível com suas contagens.")
        if not isinstance(intervalo, dict) or set(intervalo) != {"inferior", "superior"}:
            raise ValueError("Intervalo externo de Wilson inválido.")
        for lado, valor in esperado.items():
            if not math.isclose(_numero(intervalo[lado], "wilson95"), valor, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("Intervalo externo incompatível com as contagens.")
    return {"count": total, "n": n, "k": k, "coverage": cobertura,
            "precision": precisao, "wilson95": esperado}


def construir_entrega(produtos: dict[str, bytes], questoes: list[dict], taxonomia: dict) -> dict[str, bytes]:
    """Converte produtos verificados em três arquivos, sem escrever no disco.

    O estimador de precisão extrapola a taxa das publicações externas da
    seleção aninhada. Não usa os rótulos da reserva conhecida para escolher
    política, nem confunde a média da confiança com precisão observada.
    """
    if not isinstance(produtos, dict) or not isinstance(questoes, list):
        raise ValueError("Produtos devem ser um mapa e questões devem ser uma lista.")
    if any(not isinstance(q, dict) or not isinstance(q.get("id"), str) or not q["id"] for q in questoes):
        raise ValueError("Cada questão deve possuir ID textual não vazio.")
    ids = {q["id"] for q in questoes}
    if len(questoes) != _QUANTIDADE or len(ids) != _QUANTIDADE:
        raise ValueError("A entrega oficial requer exatamente 659 questões únicas.")
    politica = _ler_json(produtos, "politica.json")
    if type(politica.get("habilitada")) is not bool:
        raise ValueError("Política final deve informar habilitada booleano.")
    if not isinstance(politica.get("receita"), str) or not politica["receita"]:
        raise ValueError("Política final deve identificar a receita selecionada.")
    externa = _publicacao_externa(_ler_json(produtos, "metricas.json"))
    criterio_empirico = externa["n"] >= 10 and externa["precision"] >= 0.95
    if politica["habilitada"] and not criterio_empirico:
        raise ValueError("Publicação habilitada sem suporte mínimo e precisão externa de 95%.")

    registros, vistos = [], set()
    procedencias, publicacoes_origem = {}, {}
    avaliacao_ids = set()
    candidatas_aninhadas = 0
    for nome, origem, esperado, campo_decisao in _ORIGENS:
        ps = _ler_jsonl(produtos, nome)
        if len(ps) != esperado:
            raise ValueError(f"Produto {nome} deve conter exatamente {esperado} predições.")
        procedencias[origem] = esperado
        publicacoes_origem[origem] = 0
        for p in ps:
            identificador = p.get("id")
            if not isinstance(identificador, str) or identificador not in ids or identificador in vistos:
                raise ValueError("Predições devem ter IDs conhecidos, únicos e disjuntos entre procedências.")
            vistos.add(identificador)
            if type(p.get(campo_decisao)) is not bool:
                raise ValueError(f"Predição de {nome} exige {campo_decisao} booleano.")
            if origem == "selecao_aninhada":
                candidatas_aninhadas += int(p[campo_decisao])
            if not isinstance(p.get("receita"), str) or not p["receita"]:
                raise ValueError("Cada predição deve identificar sua receita.")
            if origem != "selecao_aninhada" and p["receita"] != politica["receita"]:
                raise ValueError("Receita da predição final diverge da política selecionada.")
            confianca = _numero(p.get("confianca"), "confiança")
            publicar = politica["habilitada"] and p[campo_decisao]
            if publicar:
                motivo = "Atende à política seletiva; confiança estimada, sem garantia individual."
            elif not politica["habilitada"]:
                motivo = "Publicação automática desabilitada pela política final."
            else:
                motivo = "Não atende à regra seletiva avaliada para esta procedência."
            registros.append({
                "id": identificador, "decisao": "publicar" if publicar else "revisar",
                "tema_central_id": p.get("tema_sugerido_id"), "extras_ids": "",
                "confianca": confianca, "motivo": motivo,
            })
            publicacoes_origem[origem] += int(publicar)
            if origem == "avaliacao_modelo100":
                avaliacao_ids.add(identificador)
    if vistos != ids:
        raise ValueError("Predições não cobrem exatamente as questões oficiais.")
    if candidatas_aninhadas != externa["n"]:
        raise ValueError("Decisões candidatas aninhadas divergem das contagens externas.")
    csv = gerar_csv(registros)
    contrato = validar_csv(csv, ids, taxonomia)
    avaliacao = [r for r in registros if r["id"] in avaliacao_ids]
    publicadas = [r for r in avaliacao if r["decisao"] == "publicar"]
    n, total = len(publicadas), len(avaliacao)
    cobertura = n / total
    extrapolar = politica["habilitada"] and n > 0 and externa["n"] > 0
    precisao_prevista = externa["precision"] if extrapolar else None
    media_confianca = math.fsum(r["confianca"] for r in publicadas) / n if n else None
    ranking_aprendido_com100 = politica["receita"] != "large_rrf20"
    qualificacao_ranking = (
        "As 559 sugestões usam ranking reajustado com 100 referências; esse reajuste não recebeu novo teste independente."
        if ranking_aprendido_com100 else
        "As 559 sugestões usam ranking RRF fixo, sem pesos aprendidos com as 100 referências. "
        "As 100 identificam a coorte de referência; 80 são usadas na seleção e calibração e "
        "20 somente no diagnóstico conhecido. Os rótulos das 20 não escolhem o RRF. "
        "Não existe novo teste independente."
    )
    previsao = {
        "schema": "previsao_m8_v1", "universo_csv": _QUANTIDADE,
        "avaliacao_total": total, "referencias_excluidas": 100,
        "receita_selecionada": politica["receita"], "politica_habilitada": politica["habilitada"],
        "ranking_aprendido_com100": ranking_aprendido_com100,
        "publicadas": n, "precisao_observada_avaliacao": None,
        "precisao_observada_avaliacao_motivo": "As 559 questões de avaliação não possuem rótulos disponíveis.",
        "precisao_prevista": precisao_prevista,
        "precisao_txt_sentinela_zero": n == 0,
        "precisao_prevista_e_extrapolacao": extrapolar,
        "precisao_metodo": (
            "Taxa empírica das publicações na seleção aninhada externa sobre 80 referências, "
            "extrapolada às publicadas entre as 559 sob hipótese de comparabilidade. "
            "Indefinida sem publicações; não é precisão observada nas 559 nem garantia de 95%."
        ),
        "precisao_intervalo": externa["wilson95"] if extrapolar else None,
        "precisao_intervalo_natureza": (
            "Wilson bilateral de 95% sobre o grupo publicado na seleção aninhada; "
            "sua extrapolação não quantifica adaptação anterior, seleção múltipla ou mudança de distribuição."
            if extrapolar else "Sem previsão de precisão para publicações; nenhum intervalo extrapolado."
        ),
        "media_confianca_publicadas": media_confianca,
        "media_confianca_interpretacao": (
            "Média das probabilidades estimadas pelo calibrador nas publicadas; "
            "diagnóstico separado da precisão empírica e da extrapolação."
        ),
        "cobertura_prevista": cobertura,
        "cobertura_intervalo": {"inferior": cobertura, "superior": cobertura},
        "cobertura_metodo": "Contagem exata das decisões nas 559 questões; exclui as 100 referências.",
        "referencia_selecao_aninhada": externa,
        "criterio_empirico_95_atendido_na_selecao_aninhada": criterio_empirico,
        "ajuste_final_testado_independentemente": False,
        "referencias_reutilizadas": True,
        "meta_95_comprovada": False,
        "qualificacoes_avaliacao": [
            "As 80 referências já orientaram módulos anteriores; a seleção aninhada M8 é exploratória.",
            "As 20 referências reservadas já eram conhecidas; não constituem holdout independente novo.",
            qualificacao_ranking,
            "Mudanças de distribuição nas questões recentes não são medidas por um conjunto rotulado recente.",
            "A decisão fora não é automatizada; baixa confiança encaminha à revisão com tema sugerido.",
        ],
        "procedencias_csv": procedencias,
        "publicacoes_por_procedencia": publicacoes_origem,
        "decisoes_avaliacao": {d: sum(r["decisao"] == d for r in avaliacao)
                              for d in ("publicar", "revisar", "fora")},
        "contrato_csv": contrato,
    }
    return {
        "publicacao.csv": csv,
        "previsao.txt": _previsao_txt(previsao),
        "previsao.json": (json.dumps(previsao, ensure_ascii=False, sort_keys=True,
                                    indent=2, allow_nan=False) + "\n").encode("utf-8"),
    }


def _previsao_txt(previsao):
    precisao = previsao["precisao_prevista"]
    intervalo = previsao["precisao_intervalo"] or {"inferior": 0.0, "superior": 1.0}
    cobertura = previsao["cobertura_prevista"]
    externa = previsao["referencia_selecao_aninhada"]
    linhas = [
        f"precisao_prevista: {precisao if precisao is not None else 0.0:.8f}",
        f"precisao_intervalo: {intervalo['inferior']:.8f}-{intervalo['superior']:.8f}",
        f"cobertura_prevista: {cobertura:.8f}",
        f"cobertura_intervalo: {cobertura:.8f}-{cobertura:.8f}",
        "",
        f"A previsão considera apenas as {previsao['avaliacao_total']} questões sem rótulos. "
        "As 100 referências humanas são excluídas dos denominadores de avaliação.",
        f"Foram publicadas {previsao['publicadas']} de {previsao['avaliacao_total']} questões. "
        "A cobertura é uma contagem exata; a precisão observada nessas questões é desconhecida.",
        "",
    ]
    if precisao is None:
        linhas += [
            "Não há questões publicadas na avaliação. A precisão entre publicadas é matematicamente "
            "indefinida por denominador zero. O valor 0.00000000 da primeira linha é uma sentinela "
            "numérica do formato, não uma previsão de 0% de acerto. O JSON registra null.",
            "O intervalo 0.00000000-1.00000000 significa ausência de informação sobre precisão "
            "entre publicadas; não é um intervalo de confiança estimado. Cobertura zero não "
            "comprova atendimento à meta de 95%.",
        ]
    else:
        linhas += [
            f"A precisão prevista extrapola {externa['k']} acertos em {externa['n']} publicações "
            "na seleção aninhada externa sobre 80 referências. É uma taxa empírica de grupo, "
            "transportada sob hipótese de comparabilidade; não é precisão observada nas 559.",
            previsao["precisao_intervalo_natureza"],
            f"A média separada das confianças estimadas nas publicadas é "
            f"{previsao['media_confianca_publicadas']:.8f}; não foi confundida com precisão empírica.",
        ]
    linhas += ["", *previsao["qualificacoes_avaliacao"],
               "A meta de 95% não é declarada comprovada e não há garantia individual de acerto.", ""]
    return "\n".join(linhas).encode("utf-8")
