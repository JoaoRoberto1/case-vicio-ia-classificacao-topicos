"""Leitura e preparação dos anexos, sem classificação, IA ou gravação.

Os campos de origem e a coorte são metadados de diagnóstico. A folha-verdade
é lida exclusivamente do anexo fornecido; esta preparação valida sua estrutura,
não julga a correção temática de seus rótulos.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .taxonomia import carregar_taxonomia
from .texto import analisar_texto


CAMPOS_QUESTAO = {
    "id", "enunciado_html", "comando", "alternativas",
    "disciplina_origem", "assunto_origem",
}
COLUNAS_FOLHA_VERDADE = (
    "id", "tema_central_id", "tema_central_caminho",
    "extras_ids", "fora_da_taxonomia",
)


def carregar_questoes(caminho: Path) -> list[dict]:
    """Leia todas as linhas e recuse dados incompletos ou IDs repetidos."""
    caminho = Path(caminho)
    registros: list[dict] = []
    ids: set[str] = set()

    def objeto_sem_duplicatas(pares: list[tuple]) -> dict:
        objeto: dict = {}
        for chave, valor in pares:
            if chave in objeto:
                raise ValueError(f"Chave JSON duplicada: {chave!r}.")
            objeto[chave] = valor
        return objeto

    # A iteração física não divide U+2028/U+0085 dentro de strings JSON.
    with caminho.open(encoding="utf-8-sig") as arquivo:
        linhas = list(arquivo)
    for numero, linha in enumerate(linhas, 1):
        if not linha.strip():
            raise ValueError(f"Linha {numero} vazia em {caminho.name}.")
        try:
            registro = json.loads(linha, object_pairs_hook=objeto_sem_duplicatas)
        except (json.JSONDecodeError, ValueError) as erro:
            raise ValueError(
                f"JSON inválido em {caminho.name}, linha {numero}: {erro}"
            ) from erro
        if not isinstance(registro, dict) or set(registro) != CAMPOS_QUESTAO:
            raise ValueError(f"Campos inesperados em {caminho.name}, linha {numero}.")
        for campo in CAMPOS_QUESTAO - {"alternativas"}:
            if not isinstance(registro[campo], str):
                raise ValueError(f"Campo {campo} deve ser texto na linha {numero}.")
        identificador = registro["id"]
        if not identificador.strip() or identificador != identificador.strip() or identificador in ids:
            raise ValueError(f"ID vazio, com espaços ou duplicado na linha {numero}: {identificador!r}.")
        alternativas = registro["alternativas"]
        if not isinstance(alternativas, dict) or len(alternativas) < 2:
            raise ValueError(f"Questão {identificador}: esperadas pelo menos duas alternativas.")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str)
               for k, v in alternativas.items()):
            raise ValueError(f"Questão {identificador}: alternativas devem mapear rótulos para textos.")
        ids.add(identificador)
        registros.append(registro)
    if not registros:
        raise ValueError(f"Nenhuma questão em {caminho.name}.")
    return registros


def _coorte(identificador: str) -> str:
    """Identifica a procedência documentada; não constitui atributo temático."""
    if re.fullmatch(r"Q[0-9]{4}", identificador):
        numero = int(identificador[1:])
        if 1 <= numero <= 359:
            return "historicas"
        if 360 <= numero <= 659:
            return "recentes"
    return "nao_identificada"


def preparar_questao(original: dict, numero_linha: int) -> dict:
    """Preserva conteúdo e metadados, sem acrescentar sugestão de tema."""
    campos = {
        "enunciado": analisar_texto(original["enunciado_html"]),
        "comando": analisar_texto(original["comando"]),
    }
    alternativas = {rotulo: analisar_texto(texto)
                    for rotulo, texto in original["alternativas"].items()}
    avisos: list[str] = []
    for campo, resultado in campos.items():
        avisos.extend(f"{campo}:{aviso}" for aviso in resultado["avisos"])
        if not resultado["texto"]:
            avisos.append(f"{campo}:vazio_apos_preparacao")
    for rotulo, resultado in alternativas.items():
        avisos.extend(f"alternativa_{rotulo}:{aviso}" for aviso in resultado["avisos"])
        if not resultado["texto"]:
            avisos.append(f"alternativa_{rotulo}:vazia_apos_preparacao")
    for campo in ("disciplina_origem", "assunto_origem"):
        if not original[campo].strip():
            avisos.append(f"{campo}:vazio")
    enunciado = campos["enunciado"]["texto"]
    comando = campos["comando"]["texto"]
    # Texto curto é apenas um sinal estrutural; nunca determina fora/revisar.
    if len(enunciado) < 80:
        avisos.append("enunciado:curto_conferir_comando_e_alternativas")
    textos_alternativas = {rotulo: item["texto"] for rotulo, item in alternativas.items()}
    texto_completo = (
        f"ENUNCIADO\n{enunciado}\n\nCOMANDO\n{comando}\n\nALTERNATIVAS\n"
        + "\n".join(f"{rotulo}) {texto}" for rotulo, texto in textos_alternativas.items())
    )
    resultados = [*campos.values(), *alternativas.values()]
    canonico = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "id": original["id"],
        "enunciado": enunciado,
        "comando": comando,
        "alternativas": textos_alternativas,
        "texto_completo": texto_completo,
        "disciplina_origem": original["disciplina_origem"],
        "assunto_origem": original["assunto_origem"],
        "coorte": _coorte(original["id"]),
        "referencia_origem": {
            "arquivo": "questoes.jsonl", "linha": numero_linha,
            "sha256_registro_canonico": hashlib.sha256(canonico.encode("utf-8")).hexdigest(),
        },
        "caracteres_brutos": sum(r["caracteres_brutos"] for r in resultados),
        "caracteres_limpos": sum(r["caracteres_limpos"] for r in resultados),
        "avisos": sorted(set(avisos)),
    }


def carregar_folha_verdade(
    caminho: Path, questoes: list[dict], taxonomia: dict
) -> list[dict]:
    """Valida os rótulos fornecidos e deriva a disciplina do tema central.

    O caminho legível é preservado como veio no CSV. Não é interpretado como
    ID nem usado para corrigir ou escolher temas. A ordem das linhas é mantida.
    """
    caminho = Path(caminho)
    if not isinstance(taxonomia, dict) or not isinstance(taxonomia.get("por_id"), dict):
        raise ValueError("Taxonomia preparada deve fornecer o índice por_id.")
    temas = taxonomia["por_id"]
    ids_questoes: set[str] = set()
    for questao in questoes:
        identificador = questao.get("id") if isinstance(questao, dict) else None
        if (not isinstance(identificador, str) or not identificador.strip()
                or identificador != identificador.strip() or identificador in ids_questoes):
            raise ValueError("Questões devem ter IDs textuais únicos, não vazios e sem espaços.")
        ids_questoes.add(identificador)

    rotulos: list[dict] = []
    vistos: set[str] = set()
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, strict=True)
        try:
            if leitor.fieldnames != list(COLUNAS_FOLHA_VERDADE):
                raise ValueError(
                    "Esquema da folha-verdade inválido: esperado exatamente "
                    + ",".join(COLUNAS_FOLHA_VERDADE) + ", nessa ordem."
                )
            for linha in leitor:
                contexto = f"Folha-verdade, linha {leitor.line_num}"
                if None in linha or any(valor is None for valor in linha.values()):
                    raise ValueError(f"{contexto}: quantidade de campos diferente do cabeçalho.")
                identificador = linha["id"]
                if identificador in vistos:
                    raise ValueError(f"{contexto}: ID duplicado {identificador!r}.")
                if identificador not in ids_questoes:
                    raise ValueError(f"{contexto}: ID inexistente nas questões: {identificador!r}.")
                if linha["fora_da_taxonomia"] not in {"0", "1"}:
                    raise ValueError(f"{contexto}: fora_da_taxonomia deve ser 0 ou 1.")
                fora = linha["fora_da_taxonomia"] == "1"
                central = linha["tema_central_id"]
                extras = linha["extras_ids"].split(";") if linha["extras_ids"] else []
                if any(not extra or extra != extra.strip() for extra in extras):
                    raise ValueError(f"{contexto}: extras_ids contém ID vazio ou com espaços.")
                if len(extras) != len(set(extras)) or central and central in extras:
                    raise ValueError(f"{contexto}: extras_ids duplicados ou repetindo o tema central.")
                if fora:
                    if central or extras:
                        raise ValueError(f"{contexto}: fora_da_taxonomia=1 exige central e extras vazios.")
                    disciplina = "fora"
                else:
                    if not central:
                        raise ValueError(f"{contexto}: fora_da_taxonomia=0 exige tema central.")
                    for tema_id in [central, *extras]:
                        tema = temas.get(tema_id)
                        if not isinstance(tema, dict) or tema.get("status") != "active":
                            raise ValueError(f"{contexto}: tema inexistente ou inativo: {tema_id!r}.")
                    disciplina = temas[central]["disciplina"]
                vistos.add(identificador)
                rotulos.append({
                    "id": identificador,
                    "tema_central_id": central,
                    "tema_central_caminho": linha["tema_central_caminho"],
                    "extras_ids": extras,
                    "fora_da_taxonomia": fora,
                    "disciplina": disciplina,
                })
        except csv.Error as erro:
            raise ValueError(f"CSV da folha-verdade inválido na linha {leitor.line_num}: {erro}") from erro
    if not rotulos:
        raise ValueError("Folha-verdade sem registros.")
    return rotulos


def preparar_dados(entrada: Path) -> dict:
    """Lê três anexos e devolve os dados preparados, sem escrever arquivos."""
    entrada = Path(entrada)
    for nome in ("questoes.jsonl", "temas.csv", "folha_verdade.csv"):
        if not (entrada / nome).is_file():
            raise ValueError(f"Arquivo de entrada ausente: {nome}.")
    originais = carregar_questoes(entrada / "questoes.jsonl")
    taxonomia = carregar_taxonomia(entrada / "temas.csv")
    questoes = [preparar_questao(q, i) for i, q in enumerate(originais, 1)]
    rotulos = carregar_folha_verdade(entrada / "folha_verdade.csv", questoes, taxonomia)
    coortes = {q["id"]: q["coorte"] for q in questoes}
    avisos = Counter(aviso for q in questoes for aviso in q["avisos"])
    diagnostico = {
        "schema_version": 1,
        "questoes": {
            "total": len(questoes),
            "ids_duplicados": 0,
            "coortes": dict(sorted(Counter(coortes.values()).items())),
            "comando_vazio_original": sum(not q["comando"].strip() for q in originais),
            "comando_vazio_preparado": sum(not q["comando"] for q in questoes),
            "assunto_origem_vazio": sum(not q["assunto_origem"].strip() for q in originais),
            "disciplina_origem_vazia": sum(not q["disciplina_origem"].strip() for q in originais),
            "quantidade_alternativas": dict(sorted(
                Counter(str(len(q["alternativas"])) for q in originais).items()
            )),
            "disciplinas_origem": dict(sorted(
                Counter(q["disciplina_origem"] for q in originais).items()
            )),
            "caracteres_brutos": sum(q["caracteres_brutos"] for q in questoes),
            "caracteres_limpos": sum(q["caracteres_limpos"] for q in questoes),
            "questoes_com_avisos": sum(bool(q["avisos"]) for q in questoes),
            "avisos": dict(sorted(avisos.items())),
        },
        "taxonomia": taxonomia["diagnostico"],
        "rotulos": {
            "total": len(rotulos),
            "fora_da_taxonomia": sum(r["fora_da_taxonomia"] for r in rotulos),
            "por_disciplina": dict(sorted(Counter(r["disciplina"] for r in rotulos).items())),
            "por_coorte": dict(sorted(Counter(coortes[r["id"]] for r in rotulos).items())),
            "questoes_sem_rotulo": len(questoes) - len(rotulos),
        },
        "limites": [
            "Validação estrutural; não classifica questões nem julga rótulos fornecidos.",
            "Origem e coorte são metadados de diagnóstico, não escolhas ou evidências de tema.",
            "A disciplina dos rótulos vem da taxonomia; para fora, usa-se 'fora'.",
            "O caminho legível da folha-verdade é preservado sem corrigir IDs.",
            "A limpeza não reconstitui OCR, conteúdo de imagens ou texto ausente.",
        ],
    }
    return {
        "questoes": questoes,
        "taxonomia": taxonomia,
        "rotulos": rotulos,
        "diagnostico": diagnostico,
    }
