"""Leitura e diagnóstico da árvore, sem corrigir ou fundir seus rótulos.

Não há regra de classificação ou de acerto hierárquico neste módulo. A marca
``elegivel`` representa somente ``status == 'active'``; não é uma recomendação
de publicação. Todos os campos do CSV permanecem como strings originais.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


COLUNAS_TAXONOMIA = (
    "tema_id", "parent_id", "disciplina", "nivel", "titulo", "caminho",
    "descricao", "status",
)


def _ler_registros(caminho: Path) -> list[dict]:
    """Recusa um CSV incompleto ou estruturalmente ambíguo antes de enriquecê-lo."""
    registros = []
    with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, strict=True)
        try:
            cabecalho = leitor.fieldnames
        except csv.Error as erro:
            raise ValueError(f"Cabeçalho CSV da taxonomia inválido: {erro}") from erro
        if not cabecalho:
            raise ValueError("Taxonomia sem cabeçalho CSV.")
        if len(cabecalho) != len(set(cabecalho)):
            raise ValueError("Taxonomia com colunas duplicadas no cabeçalho.")
        ausentes = sorted(set(COLUNAS_TAXONOMIA) - set(cabecalho))
        extras = sorted(set(cabecalho) - set(COLUNAS_TAXONOMIA))
        if ausentes or extras:
            raise ValueError(
                f"Esquema da taxonomia inválido: colunas ausentes={ausentes}; "
                f"colunas inesperadas={extras}."
            )
        try:
            for registro in leitor:
                if None in registro or any(valor is None for valor in registro.values()):
                    raise ValueError(
                        f"Linha {leitor.line_num}: quantidade de campos diferente do cabeçalho."
                    )
                for campo in ("tema_id", "disciplina", "nivel", "titulo", "status"):
                    if not registro[campo].strip():
                        raise ValueError(f"Linha {leitor.line_num}: campo {campo!r} vazio.")
                for campo in ("tema_id", "parent_id"):
                    if registro[campo] != registro[campo].strip():
                        raise ValueError(
                            f"Linha {leitor.line_num}: {campo} contém espaços nas extremidades."
                        )
                if registro["nivel"] not in {"0", "1", "2"}:
                    raise ValueError(
                        f"Tema {registro['tema_id']}: nível inválido {registro['nivel']!r}; "
                        "esperado 0, 1 ou 2."
                    )
                if registro["status"] not in {"active", "inactive"}:
                    raise ValueError(
                        f"Tema {registro['tema_id']}: status inválido {registro['status']!r}; "
                        "esperado active ou inactive."
                    )
                registros.append(registro)
        except csv.Error as erro:
            raise ValueError(f"CSV da taxonomia inválido na linha {leitor.line_num}: {erro}") from erro
    if not registros:
        raise ValueError("Taxonomia sem registros.")
    return registros


def carregar_taxonomia(caminho: Path) -> dict:
    """Retorna registros enriquecidos, índice por ID e diagnóstico serializável.

    Pais e filhos seguem a ordem do CSV. Ancestrais excluem o próprio nó e
    aparecem da raiz para o pai. Erros estruturais geram ``ValueError``; a
    função nunca escreve arquivos. Caminhos divergentes são avisos, sem
    alteração do valor declarado. Descrições de metadados são identificadas
    pelos prefixos do material de entrada, sem interpretar seu conteúdo.
    """
    registros = _ler_registros(Path(caminho))
    por_id: dict[str, dict] = {}
    for registro in registros:
        tema_id = registro["tema_id"]
        if tema_id in por_id:
            raise ValueError(f"tema_id duplicado na taxonomia: {tema_id!r}.")
        por_id[tema_id] = registro
        registro.update(ancestrais_ids=[], filhos_ids=[], avisos=[])
        registro["elegivel"] = registro["status"] == "active"

    for registro in registros:
        pai = registro["parent_id"]
        if pai:
            if pai not in por_id:
                raise ValueError(f"Tema {registro['tema_id']}: parent_id {pai!r} inexistente.")
            por_id[pai]["filhos_ids"].append(registro["tema_id"])

    # Percurso iterativo também detecta cadeias malformadas muito profundas,
    # sem depender do limite de recursão do Python.
    resolvidos: set[str] = set()
    for tema_id in por_id:
        cadeia: list[str] = []
        posicoes: dict[str, int] = {}
        atual = tema_id
        while atual and atual not in resolvidos:
            if atual in posicoes:
                ciclo = cadeia[posicoes[atual]:] + [atual]
                raise ValueError(f"Ciclo na taxonomia: {' -> '.join(ciclo)}.")
            posicoes[atual] = len(cadeia)
            cadeia.append(atual)
            atual = por_id[atual]["parent_id"]
        for atual in reversed(cadeia):
            registro = por_id[atual]
            pai = registro["parent_id"]
            ancestrais = por_id[pai]["ancestrais_ids"] + [pai] if pai else []
            registro["ancestrais_ids"] = ancestrais
            resolvidos.add(atual)

    alertas_caminho = []
    ativos_com_ancestral_inativo = []
    for registro in registros:
        tema_id = registro["tema_id"]
        ancestrais = registro["ancestrais_ids"]
        if int(registro["nivel"]) != len(ancestrais):
            raise ValueError(
                f"Tema {tema_id}: nível {registro['nivel']} incompatível com "
                f"profundidade {len(ancestrais)}; raiz deve ter nível 0."
            )
        raiz = por_id[ancestrais[0]] if ancestrais else registro
        if registro["disciplina"] != raiz["disciplina"]:
            raise ValueError(
                f"Tema {tema_id}: disciplina {registro['disciplina']!r} difere "
                f"da disciplina da raiz {raiz['tema_id']} ({raiz['disciplina']!r})."
            )
        registro["caminho_calculado"] = " > ".join(
            por_id[identificador]["titulo"] for identificador in ancestrais + [tema_id]
        )
        if registro["caminho"] != registro["caminho_calculado"]:
            registro["avisos"].append("caminho_divergente")
            alertas_caminho.append({
                "tema_id": tema_id,
                "declarado": registro["caminho"],
                "calculado": registro["caminho_calculado"],
            })
        if registro["elegivel"] and any(
            por_id[identificador]["status"] == "inactive" for identificador in ancestrais
        ):
            registro["avisos"].append("ancestral_inativo")
            ativos_com_ancestral_inativo.append(tema_id)

    descricoes: dict[str, list[str]] = {"vazias": [], "metadados": [], "outras": []}
    titulos: dict[str, list[dict]] = defaultdict(list)
    for registro in registros:
        descricao = registro["descricao"].strip()
        if not descricao:
            categoria = "vazias"
            registro["avisos"].append("descricao_vazia")
        elif descricao.startswith(("Disciplina (root).", "Subtema de ")):
            categoria = "metadados"
            registro["avisos"].append("descricao_de_metadados")
        else:
            categoria = "outras"
        descricoes[categoria].append(registro["tema_id"])
        titulos[registro["titulo"].strip().casefold()].append(registro)

    titulos_repetidos = []
    for normalizado, grupo in titulos.items():
        if len(grupo) > 1:
            for registro in grupo:
                registro["avisos"].append("titulo_repetido")
            titulos_repetidos.append({
                "titulo_normalizado": normalizado,
                "ids": [registro["tema_id"] for registro in grupo],
                "caminhos": [registro["caminho_calculado"] for registro in grupo],
            })

    disciplinas = dict(Counter(registro["disciplina"] for registro in registros))
    diagnostico = {
        "total": len(registros),
        "niveis": dict(Counter(registro["nivel"] for registro in registros)),
        "status": dict(Counter(registro["status"] for registro in registros)),
        "disciplinas": disciplinas,
        "total_disciplinas": len(disciplinas),
        "raizes_ids": [registro["tema_id"] for registro in registros if not registro["parent_id"]],
        "inativos_ids": [registro["tema_id"] for registro in registros if not registro["elegivel"]],
        "descricoes": {
            categoria: {"total": len(ids), "ids": ids} for categoria, ids in descricoes.items()
        },
        "criterio_descricao_metadados": "Prefixo 'Disciplina (root).' ou 'Subtema de '.",
        "titulos_repetidos": titulos_repetidos,
        "alertas_caminho": alertas_caminho,
        "ativos_com_ancestral_inativo_ids": ativos_com_ancestral_inativo,
        "validacao_estrutural": {
            "ids_unicos": True,
            "pais_existentes": True,
            "sem_ciclos": True,
            "niveis_coerentes": True,
            "todos_alcancam_raiz": True,
            "disciplinas_coerentes": True,
        },
    }
    return {"registros": registros, "por_id": por_id, "diagnostico": diagnostico}


def exportar_arvore(taxonomia: dict) -> str:
    """Produz texto legível por ramo, incluindo nós inativos e seus IDs."""
    linhas = ["Árvore de temas — IDs e status originais", ""]
    por_id = taxonomia["por_id"]
    pendentes = list(reversed(taxonomia["diagnostico"]["raizes_ids"]))
    while pendentes:
        tema_id = pendentes.pop()
        registro = por_id[tema_id]
        recuo = "  " * len(registro["ancestrais_ids"])
        titulo = " ".join(registro["titulo"].splitlines())
        linhas.append(f"{recuo}- [{tema_id}] {titulo} ({registro['status']})")
        pendentes.extend(reversed(registro["filhos_ids"]))
    return "\n".join(linhas) + "\n"
