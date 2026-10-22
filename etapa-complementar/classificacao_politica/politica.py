"""Grade fixa de abstenção; concordância algorítmica não é validação humana.

Este módulo não lê textos, executa modelos ou atribui temas. O aprendizado
da política usa somente acertos booleanos recebidos. A aplicação ignora
rótulos, acertos, partições e metadados de referência.
"""

from __future__ import annotations

import math

from classificacao_catalogo.selecao import medir


SCHEMA = "politica_seletiva_m9_v1"
ANCORA = "sinais_large"
RECEITAS_CONCORDANCIA = ("sinais_small", "large_rrf20", ANCORA)
CORTES = (0.8, 0.9, 0.95)
PRECISAO_MINIMA = 0.95
CAMPOS_CONFIANCA = frozenset({"confianca", "confianca_oof"})


def _texto(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo} deve ser um texto não vazio.")
    return valor


def _probabilidade(valor: object, campo: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{campo} deve ser uma probabilidade numérica.")
    try:
        numero = float(valor)
    except (OverflowError, ValueError):
        raise ValueError(f"{campo} excede o intervalo numérico.") from None
    if not math.isfinite(numero) or not 0 <= numero <= 1:
        raise ValueError(f"{campo} deve ser finito e pertencer a [0, 1].")
    return numero


def _particao(valor: object) -> int | str:
    if type(valor) is int and valor >= 0:
        return valor
    if isinstance(valor, str) and valor.strip():
        return valor
    raise ValueError("particao_interna deve ser inteiro não negativo ou texto não vazio.")


def _validar_registros(ps: object, *, exigir_particao: bool = False) -> dict:
    if not isinstance(ps, list):
        raise ValueError("As predições devem ser uma lista.")
    por_id = {}
    presencas = set()
    for p in ps:
        if not isinstance(p, dict):
            raise ValueError("Cada predição deve ser um objeto.")
        identificador = _texto(p.get("id"), "id")
        if identificador in por_id:
            raise ValueError("IDs de predição devem ser únicos.")
        por_id[identificador] = p
        presenca = "particao_interna" in p
        presencas.add(presenca)
        if presenca:
            _particao(p["particao_interna"])
        elif exigir_particao:
            raise ValueError("A seleção requer particao_interna em todos os registros.")
    if len(presencas) > 1:
        raise ValueError("A partição deve estar presente em todos os registros ou em nenhum.")
    return por_id


def preparar(resultados: dict[str, list[dict]]) -> list[dict]:
    """Une por ID as três receitas e anexa concordância exata ao tema âncora.

    Receitas adicionais não participam. Partições podem estar ausentes em
    uma coorte final; quando presentes, devem coincidir nas três receitas.
    Nenhum acerto, rótulo ou texto é consultado para calcular concordância.
    """
    if not isinstance(resultados, dict) or not set(RECEITAS_CONCORDANCIA) <= set(resultados):
        raise ValueError("São necessárias as três receitas fixadas para concordância.")
    mapas = {}
    for nome in RECEITAS_CONCORDANCIA:
        mapa = _validar_registros(resultados[nome])
        if not mapa:
            raise ValueError("Cada receita deve conter predições.")
        for p in mapa.values():
            _texto(p.get("tema_sugerido_id"), "tema_sugerido_id")
            if "receita" in p and p["receita"] != nome:
                raise ValueError("A receita do registro diverge da chave do conjunto.")
        mapas[nome] = mapa
    ids = set(mapas[ANCORA])
    if any(set(mapa) != ids for mapa in mapas.values()):
        raise ValueError("As receitas devem cobrir exatamente os mesmos IDs.")
    saida = []
    for identificador in sorted(ids):
        linha = mapas[ANCORA][identificador]
        for mapa in mapas.values():
            outra = mapa[identificador]
            if ("particao_interna" in linha) != ("particao_interna" in outra):
                raise ValueError("As receitas devem informar as mesmas partições.")
            if "particao_interna" in linha:
                a, b = linha["particao_interna"], outra["particao_interna"]
                if type(a) is not type(b) or a != b:
                    raise ValueError("Um ID pertence a partições diferentes entre receitas.")
        acordo = all(mapa[identificador]["tema_sugerido_id"] == linha["tema_sugerido_id"]
                     for mapa in mapas.values())
        saida.append({**linha, "concordancia_algoritmos": acordo})
    return saida


def _regra(corte: float, exige_concordancia: bool) -> str:
    nome = f"confianca_p{round(100 * corte)}"
    return nome + ("_concordancia" if exige_concordancia else "")


def _politica(corte: float, exige_concordancia: bool) -> dict:
    return {
        "schema": SCHEMA, "receita": ANCORA, "regra": _regra(corte, exige_concordancia),
        "corte": corte, "exige_concordancia": exige_concordancia, "habilitada": True,
    }


def _validar_politica(politica: object) -> None:
    if (not isinstance(politica, dict) or politica.get("schema") != SCHEMA
            or not {"schema", "receita", "regra", "corte", "exige_concordancia", "habilitada"} <= set(politica)
            or politica.get("receita") != ANCORA
            or type(politica.get("habilitada")) is not bool
            or type(politica.get("exige_concordancia")) is not bool):
        raise ValueError("Esquema ou indicadores da política M9 inválidos.")
    if politica.get("regra") is None:
        if (politica["habilitada"] or "corte" not in politica
                or politica["corte"] is not None or politica["exige_concordancia"]):
            raise ValueError("A política sem regra deve ser o fallback desabilitado.")
        return
    corte = _probabilidade(politica.get("corte"), "corte")
    if corte not in CORTES or politica["regra"] != _regra(corte, politica["exige_concordancia"]):
        raise ValueError("Regra ou corte fora da grade fixa M9.")


def aplicar(p: dict, politica: dict, campo: str = "confianca") -> bool:
    """Aplica apenas confiança e concordância; valida mesmo se desabilitada."""
    _validar_politica(politica)
    if not isinstance(campo, str) or campo not in CAMPOS_CONFIANCA or not isinstance(p, dict):
        raise ValueError("Predição ou campo de confiança inválido.")
    confianca = _probabilidade(p.get(campo), campo)
    if type(p.get("concordancia_algoritmos")) is not bool:
        raise ValueError("concordancia_algoritmos deve ser booleano.")
    if not politica["habilitada"]:
        return False
    return (confianca >= politica["corte"]
            and (not politica["exige_concordancia"] or p["concordancia_algoritmos"]))


def resumir(ps: list[dict], aceitos: list[bool]) -> dict:
    """Resume acertos fornecidos, inclusive folds sem publicações, sem inferi-los."""
    _validar_registros(ps)
    resumo = medir(ps, aceitos)
    particoes = sorted({p["particao_interna"] for p in ps if "particao_interna" in p},
                       key=lambda valor: (type(valor).__name__, str(valor)))
    por_particao = []
    for particao in particoes:
        pares = [(p, aceito) for p, aceito in zip(ps, aceitos)
                 if type(p["particao_interna"]) is type(particao) and p["particao_interna"] == particao]
        por_particao.append({"particao": particao,
                             **medir([p for p, _ in pares], [a for _, a in pares])})
    return {**resumo, "por_particao": por_particao,
            "minimo_publicacoes_particao": min((p["n"] for p in por_particao), default=0)}


def curvas(ps: list[dict], campo: str = "confianca_oof") -> list[dict]:
    """Mede exatamente seis filtros predefinidos; não altera os cortes."""
    _validar_registros(ps)
    if not isinstance(campo, str) or campo not in CAMPOS_CONFIANCA:
        raise ValueError("Campo de confiança inválido.")
    curvas_fixas = []
    for corte in CORTES:
        for exige_concordancia in (False, True):
            politica = _politica(corte, exige_concordancia)
            resumo = resumir(ps, [aplicar(p, politica, campo) for p in ps])
            elegivel = resumo["n"] > 0 and resumo["precision"] >= PRECISAO_MINIMA
            curvas_fixas.append({**politica, **resumo, "habilitada": elegivel})
    return curvas_fixas


def selecionar(ps: list[dict]) -> dict:
    """Seleciona pela grade OOF, sem mínimo arbitrário de dez publicações.

    Prioridade: quantidade, precisão, menor suporte entre folds, regra
    simples, corte maior. A precisão interna não certifica a precisão futura.
    """
    _validar_registros(ps, exigir_particao=True)
    if not ps:
        raise ValueError("A seleção requer predições não vazias.")
    diagnosticos = curvas(ps, "confianca_oof")
    elegiveis = [p for p in diagnosticos if p["habilitada"]]
    if elegiveis:
        escolhida = min(elegiveis, key=lambda p: (
            -p["n"], -p["precision"], -p["minimo_publicacoes_particao"],
            p["exige_concordancia"], -p["corte"],
        ))
    else:
        escolhida = {
            "schema": SCHEMA, "receita": ANCORA, "regra": None, "corte": None,
            "exige_concordancia": False, "habilitada": False,
            **resumir(ps, [False] * len(ps)),
        }
    return {**escolhida, "diagnosticos": diagnosticos}
