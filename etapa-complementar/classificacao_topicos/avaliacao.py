"""Regra estrutural de acerto, sem classificação ou julgamento do conteúdo."""

from collections.abc import Mapping


def tema_aceito(
    tema_id: str,
    rotulo: Mapping,
    taxonomia: Mapping,
    modo: str = "ramo",
) -> bool:
    """Compara uma sugestão com um rótulo fornecido pela equipe.

    ``ramo`` aceita igualdade ou ancestralidade em qualquer direção;
    ``imediato`` limita a relação a pai/filho direto; ``exato`` só aceita
    igualdade. Irmãos nunca são aceitos apenas por compartilharem um pai.
    Temas ausentes ou inativos não são aceitos em nenhum modo.
    """
    if modo not in {"ramo", "imediato", "exato"}:
        raise ValueError(f"Modo de avaliação desconhecido: {modo!r}")
    if rotulo.get("fora_da_taxonomia", False):
        return False

    por_id = taxonomia["por_id"]
    sugerido = por_id.get(tema_id)
    if sugerido is None or sugerido.get("status") != "active":
        return False

    referencias = [rotulo.get("tema_central_id", "")]
    referencias.extend(rotulo.get("extras_ids", []))
    for referencia_id in referencias:
        referencia = por_id.get(referencia_id)
        if referencia is None or referencia.get("status") != "active":
            continue
        if tema_id == referencia_id:
            return True
        if modo == "imediato" and (
            sugerido.get("parent_id") == referencia_id
            or referencia.get("parent_id") == tema_id
        ):
            return True
        if modo == "ramo" and (
            tema_id in referencia.get("ancestrais_ids", [])
            or referencia_id in sugerido.get("ancestrais_ids", [])
        ):
            return True
    return False
