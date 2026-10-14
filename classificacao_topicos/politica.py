"""Regras operacionais de decisão, sem estimar precisão ou calibrar confiança.

O escore recebido é autodeclarado pelo classificador. O estado pendente para
sem_tema exige confirmação separada antes de qualquer decisão final fora.
"""

from __future__ import annotations

import math

from .piloto import validar_resposta


def aplicar_politica(sugestao: dict, temas_por_id: dict, ids_ambiguos: set[str], *,
                     confianca_minima: float = 0.95, max_extras_publicar: int = 1) -> dict:
    """Valida a sugestão e aplica as regras recebidas, sem consultar outras fontes.

    A ambiguidade é verificada somente no ID central explicitamente informado;
    não é propagada por parentesco nem aplicada automaticamente aos extras.
    """
    if not isinstance(temas_por_id, dict):
        raise ValueError("A taxonomia deve ser um mapa de IDs para temas.")
    identificador = sugestao.get("id") if isinstance(sugestao, dict) else None
    resposta = validar_resposta(sugestao, identificador, temas_por_id)
    if (type(confianca_minima) not in {int, float}
            or not 0 <= confianca_minima <= 1 or not math.isfinite(confianca_minima)):
        raise ValueError("A confiança mínima deve ser um número finito entre 0 e 1.")
    if type(max_extras_publicar) is not int or max_extras_publicar < 0:
        raise ValueError("O máximo de extras deve ser um inteiro não negativo.")
    if not isinstance(ids_ambiguos, set) or any(not isinstance(i, str) or not i for i in ids_ambiguos):
        raise ValueError("Os IDs ambíguos devem formar um conjunto de IDs textuais.")
    if any(not isinstance(temas_por_id.get(i), dict) or temas_por_id[i].get("status") != "active"
           for i in ids_ambiguos):
        raise ValueError("A configuração de ambiguidade contém tema inexistente ou inativo.")

    resultado = {
        "estado": "decidido", "decisao": None,
        "tema_central_id": resposta["tema_central_id"], "extras_ids": list(resposta["extras_ids"]),
        "confianca": resposta["confianca_autodeclarada"], "motivo": "", "sinais": [],
    }
    if resposta["sem_tema"]:
        resultado.update({
            "estado": "pendente_confirmacao_fora",
            "motivo": "Ausência de tema exige confirmação separada. " + resposta["motivo"].strip(),
            "sinais": ["sem_tema_sem_confirmacao"],
        })
        return resultado

    nivel = temas_por_id[resposta["tema_central_id"]].get("nivel")
    if type(nivel) is int and nivel >= 0:
        nivel_central = nivel
    elif isinstance(nivel, str) and nivel.isascii() and nivel.isdecimal():
        nivel_central = int(nivel)
    else:
        raise ValueError("O tema central deve ter nível inteiro não negativo na taxonomia.")
    regras = (
        (resposta["requer_revisao"], "revisao_solicitada", "O classificador solicitou revisão"),
        (resposta["confianca_autodeclarada"] < confianca_minima,
         "confianca_abaixo_limiar", "Confiança autodeclarada abaixo do limiar operacional"),
        (bool(resposta["temas_alternativos"]), "temas_alternativos", "Há temas alternativos"),
        (nivel_central == 0, "tema_raiz", "Tema central de nível zero"),
        (resposta["tema_central_id"] in ids_ambiguos, "tema_ambiguo", "Tema central com ambiguidade mapeada"),
        (len(resposta["extras_ids"]) > max_extras_publicar, "excesso_extras", "Quantidade de extras acima do limite"),
    )
    sinais = [codigo for presente, codigo, _ in regras if presente]
    resultado["sinais"] = sinais
    resultado["decisao"] = "revisar" if sinais else "publicar"
    if sinais:
        descricoes = [texto for presente, _, texto in regras if presente]
        resultado["motivo"] = "; ".join(descricoes) + ". " + resposta["motivo"].strip()
    return resultado
