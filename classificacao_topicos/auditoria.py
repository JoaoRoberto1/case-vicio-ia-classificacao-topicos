"""Sorteio reproduzível e pacote cego após o congelamento das decisões."""

from __future__ import annotations

from collections import Counter
import csv
import io
import math
import os
from pathlib import Path
import random
import re
import tempfile

from .lote import _ids_validos
from .piloto import (
    _carregar_preparacao, _carregar_questoes, _hash, _json, _ler_json, _validar_destino,
)


_COLUNAS = ("id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo")
_SEMENTE = 2026101401
_MAXIMO_RESTANTE = 80


def _ler(caminho: Path, hashes: dict[Path, str]) -> bytes:
    if caminho.is_symlink() or not caminho.is_file():
        raise ValueError(f"Fonte ausente ou não é arquivo comum: {caminho.name}.")
    conteudo = caminho.read_bytes()
    caminho = caminho.resolve()
    digest = _hash(conteudo)
    if caminho in hashes and hashes[caminho] != digest:
        raise ValueError("Uma fonte mudou durante a leitura da auditoria.")
    hashes[caminho] = digest
    return conteudo


def _validar_estabilidade(hashes: dict[Path, str]) -> None:
    for caminho, esperado in hashes.items():
        if caminho.is_symlink() or not caminho.is_file() or _hash(caminho.read_bytes()) != esperado:
            raise ValueError("Uma fonte da auditoria mudou durante o processamento.")


def _produtos(pasta: Path, declarados: object, hashes: dict[Path, str]) -> dict[str, bytes]:
    if not isinstance(declarados, dict) or not declarados:
        raise ValueError("Manifesto sem hashes de produtos.")
    resultado = {}
    for nome, esperado in declarados.items():
        if not isinstance(nome, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", nome) or nome in {".", ".."}:
            raise ValueError("Nome inseguro de produto no manifesto.")
        if not isinstance(esperado, str) or not re.fullmatch(r"[a-f0-9]{64}", esperado):
            raise ValueError("Hash inválido no manifesto.")
        conteudo = _ler(pasta / nome, hashes)
        if _hash(conteudo) != esperado:
            raise ValueError(f"Hash divergente no produto {nome}.")
        resultado[nome] = conteudo
    return resultado


def _preparacao(pasta: Path, hashes: dict[Path, str]) -> tuple[dict, dict, str, list[dict], dict]:
    manifesto, produtos, digest = _carregar_preparacao(pasta)
    hashes[(pasta / "manifesto.json").resolve()] = digest
    hashes.update({(pasta / nome).resolve(): valor for nome, valor in manifesto["produtos_sha256"].items()})
    questoes = _carregar_questoes(produtos["questoes_preparadas.jsonl"])
    temas = _ler_json(produtos["temas_preparados.json"].decode("utf-8-sig"))
    if not isinstance(temas, list) or not temas:
        raise ValueError("Taxonomia preparada deve ser uma lista não vazia.")
    por_id = {}
    for tema in temas:
        if not isinstance(tema, dict) or not isinstance(tema.get("tema_id"), str):
            raise ValueError("Tema preparado sem ID textual.")
        identificador = tema["tema_id"]
        if not identificador.strip() or identificador in por_id or tema.get("status") not in {"active", "inactive"}:
            raise ValueError("Tema preparado com ID ou status inválido.")
        por_id[identificador] = tema
    return manifesto, produtos, digest, questoes, por_id


def _validar_lote(manifesto: object, ids: list[str], preparacao_hash: str, produtos_preparacao: dict) -> dict:
    if (
        not isinstance(manifesto, dict) or type(manifesto.get("schema_version")) is not int
        or manifesto["schema_version"] != 1 or manifesto.get("procedimento") != "lote-v1"
    ):
        raise ValueError("Manifesto do lote inválido ou não suportado.")
    if manifesto.get("preparacao_sha256") != preparacao_hash or manifesto.get("preparacao_produtos_sha256") != produtos_preparacao:
        raise ValueError("Lote e preparação não têm os mesmos hashes.")
    if _ids_validos(manifesto.get("ids"), "lote") != ids:
        raise ValueError("O lote deve conter exatamente os IDs na ordem da preparação.")
    desenvolvimento = _ids_validos(manifesto.get("desenvolvimento_ids"), "desenvolvimento")
    if not set(desenvolvimento).issubset(ids):
        raise ValueError("Desenvolvimento contém ID fora da preparação.")
    restantes = _ids_validos(manifesto.get("restante_ids"), "restante")
    if restantes != [identificador for identificador in ids if identificador not in set(desenvolvimento)]:
        raise ValueError("Partição do lote não corresponde aos IDs preparados.")
    return manifesto


def _validar_entradas_lote(conteudo: bytes, ids: list[str]) -> None:
    encontrados = []
    for linha in conteudo.decode("utf-8-sig").split("\n"):
        if not linha.strip():
            continue
        entrada = _ler_json(linha)
        if not isinstance(entrada, dict) or set(entrada) != {"id", "prompt", "sha256_prompt"}:
            raise ValueError("Esquema inválido nas entradas do lote.")
        if not isinstance(entrada["prompt"], str) or entrada["sha256_prompt"] != _hash(entrada["prompt"].encode("utf-8")):
            raise ValueError("Hash individual de prompt inválido no lote.")
        encontrados.append(entrada["id"])
    if encontrados != ids:
        raise ValueError("Entradas do lote divergem dos IDs congelados.")


def _validar_politica(politica: object) -> dict:
    if (
        not isinstance(politica, dict) or type(politica.get("schema_version")) is not int
        or politica["schema_version"] != 1 or not isinstance(politica.get("versao"), str)
        or not politica["versao"].strip()
    ):
        raise ValueError("Política congelada inválida ou não suportada.")
    plano = politica.get("auditoria")
    if not isinstance(plano, dict) or type(plano.get("semente")) is not int or plano["semente"] != _SEMENTE:
        raise ValueError("A política deve registrar a semente de auditoria 2026101401.")
    nivel = plano.get("nivel_intervalo")
    if type(nivel) not in {int, float} or not 0 < nivel < 1 or not math.isfinite(nivel):
        raise ValueError("Nível do intervalo inválido na política de auditoria.")
    return politica


def _csv_decisoes(conteudo: bytes, ids: list[str], temas: dict) -> dict[str, dict]:
    try:
        leitor = csv.DictReader(io.StringIO(conteudo.decode("utf-8-sig"), newline=""), strict=True)
        if leitor.fieldnames != list(_COLUNAS):
            raise ValueError("CSV de decisões deve ter exatamente as seis colunas oficiais, na ordem definida.")
        decisoes = {}
        for linha in leitor:
            if None in linha or any(valor is None for valor in linha.values()):
                raise ValueError("Linha do CSV com quantidade de campos incorreta.")
            identificador = linha["id"]
            if identificador not in ids or identificador in decisoes:
                raise ValueError("CSV de decisões contém ID inexistente ou duplicado.")
            decisao = linha["decisao"]
            if decisao not in {"publicar", "revisar", "fora"}:
                raise ValueError(f"Decisão inválida em {identificador}.")
            central = linha["tema_central_id"]
            if decisao == "fora":
                if central != "":
                    raise ValueError("Decisão fora exige tema central vazio.")
            elif central not in temas or temas[central]["status"] != "active":
                raise ValueError("Publicar e revisar exigem tema central ativo.")
            extras = linha["extras_ids"].split(";") if linha["extras_ids"] else []
            if len(extras) != len(set(extras)) or central and central in extras:
                raise ValueError("Extras duplicados ou repetindo o tema central.")
            if any(extra not in temas or temas[extra]["status"] != "active" for extra in extras):
                raise ValueError("Extras devem conter somente IDs ativos válidos.")
            try:
                confianca = float(linha["confianca"])
            except ValueError as erro:
                raise ValueError("Confiança do CSV deve ser numérica.") from erro
            if not math.isfinite(confianca) or not 0 <= confianca <= 1:
                raise ValueError("Confiança do CSV deve ser finita entre 0 e 1.")
            if decisao in {"revisar", "fora"} and not linha["motivo"].strip():
                raise ValueError("Decisões revisar e fora exigem motivo.")
            decisoes[identificador] = {**linha, "extras_ids": extras, "confianca": confianca}
    except (csv.Error, UnicodeDecodeError) as erro:
        raise ValueError("CSV de decisões inválido ou sem codificação UTF-8.") from erro
    if set(decisoes) != set(ids):
        raise ValueError("CSV de decisões incompleto: deve cobrir exatamente todos os IDs preparados.")
    return decisoes


def _validar_manifesto_decisoes(
    manifesto: object, decisoes: dict, hash_csv: str, hash_preparacao: str, hash_lote: str, hash_politica: str,
    nome_csv: str = "publicacao.csv",
) -> None:
    if not isinstance(manifesto, dict) or manifesto.get("completo") is not True:
        raise ValueError("O manifesto das decisões não indica conclusão.")
    if type(manifesto.get("pendentes_fora")) is not int or manifesto["pendentes_fora"] != 0:
        raise ValueError("Há decisões fora pendentes no manifesto.")
    if manifesto.get("total_questoes") != len(decisoes):
        raise ValueError("Total de decisões incompatível com o manifesto.")
    esperados = {"manifesto_lote.json": hash_lote, "manifesto.json": hash_preparacao, "politica.json": hash_politica}
    fontes = manifesto.get("fontes_sha256")
    if not isinstance(fontes, dict) or any(fontes.get(nome) != valor for nome, valor in esperados.items()):
        raise ValueError("Manifesto das decisões não corresponde ao lote, à preparação ou à política.")
    produtos = manifesto.get("produtos_sha256")
    if not isinstance(produtos, dict) or produtos.get(nome_csv) != hash_csv:
        raise ValueError("CSV não corresponde ao hash do manifesto das decisões.")
    contagens = Counter(linha["decisao"] for linha in decisoes.values())
    if manifesto.get("decisoes") != {rotulo: contagens[rotulo] for rotulo in ("publicar", "revisar", "fora")}:
        raise ValueError("Contagens do manifesto divergem do CSV de decisões.")


def _carregar_decisoes(caminho: Path, ids: list[str], temas: dict, hashes: dict[Path, str]) -> tuple[dict, bytes, bytes | None, Path]:
    arquivo = caminho / "publicacao.csv" if caminho.is_dir() else caminho
    csv_bytes = _ler(arquivo, hashes)
    decisoes = _csv_decisoes(csv_bytes, ids, temas)
    manifesto_path = arquivo.parent / "manifesto_decisoes.json"
    manifesto_bytes = None
    if manifesto_path.exists() or manifesto_path.is_symlink():
        manifesto_bytes = _ler(manifesto_path, hashes)
        manifesto = _ler_json(manifesto_bytes.decode("utf-8-sig"))
        if not isinstance(manifesto, dict):
            raise ValueError("Manifesto de decisões deve ser um objeto JSON.")
        _produtos(arquivo.parent, manifesto.get("produtos_sha256"), hashes)
    return decisoes, csv_bytes, manifesto_bytes, arquivo


def _selecionar(ids: list[str], desenvolvimento_ids: list[str], decisoes: dict) -> tuple[dict, list[str], list[str]]:
    desenvolvimento = set(desenvolvimento_ids)
    publicadas = [identificador for identificador in ids if decisoes[identificador]["decisao"] == "publicar"]
    populacao_d = [identificador for identificador in publicadas if identificador in desenvolvimento]
    populacao_r = [identificador for identificador in publicadas if identificador not in desenvolvimento]
    selecionados_r = random.Random(_SEMENTE).sample(populacao_r, min(_MAXIMO_RESTANTE, len(populacao_r)))
    estratos = {
        "desenvolvimento": {"N": len(populacao_d), "n": len(populacao_d), "populacao_ids": populacao_d,
                            "selecionados_ids": list(populacao_d), "metodo": "censo"},
        "restante": {"N": len(populacao_r), "n": len(selecionados_r), "populacao_ids": populacao_r,
                     "selecionados_ids": selecionados_r,
                     "metodo": "censo" if len(selecionados_r) == len(populacao_r) else "amostra_aleatoria_simples_sem_reposicao"},
    }
    return estratos, populacao_d + selecionados_r, publicadas


def preparar_auditoria(preparacao: Path, lote: Path, decisoes: Path, politica: Path, saida: Path) -> dict:
    """Valida o lote inteiro antes de sortear; nunca lê recibos de modelos."""
    preparacao, saida = _validar_destino(Path(preparacao), Path(saida))
    lote, decisoes, politica = Path(lote).resolve(), Path(decisoes), Path(politica)
    if saida == lote or lote in saida.parents or saida in lote.parents:
        raise ValueError("A pasta da auditoria deve ser separada do lote.")
    if saida.exists() and any(saida.iterdir()):
        raise ValueError("A auditoria exige uma nova pasta vazia; não sobrescreva uma seleção congelada.")
    hashes: dict[Path, str] = {}
    m_preparacao, produtos_preparacao, hash_preparacao, questoes, temas = _preparacao(preparacao, hashes)
    ids = [questao["id"] for questao in questoes]
    lote_bytes = _ler(lote / "manifesto_lote.json", hashes)
    hash_lote = _hash(lote_bytes)
    m_lote = _validar_lote(_ler_json(lote_bytes.decode("utf-8-sig")), ids, hash_preparacao, m_preparacao["produtos_sha256"])
    produtos_lote = _produtos(lote, m_lote.get("produtos_sha256"), hashes)
    if "entradas.jsonl" not in produtos_lote:
        raise ValueError("Manifesto do lote não cobre suas entradas.")
    _validar_entradas_lote(produtos_lote["entradas.jsonl"], ids)
    politica_bytes = _ler(politica, hashes)
    m_politica = _validar_politica(_ler_json(politica_bytes.decode("utf-8-sig")))
    por_id_decisoes, csv_bytes, m_decisoes_bytes, arquivo_csv = _carregar_decisoes(decisoes, ids, temas, hashes)
    fontes = {"publicacao.csv": _hash(csv_bytes), "politica.json": _hash(politica_bytes),
              "manifesto.json": hash_preparacao, "manifesto_lote.json": hash_lote}
    if m_decisoes_bytes is not None:
        _validar_manifesto_decisoes(_ler_json(m_decisoes_bytes.decode("utf-8-sig")), por_id_decisoes,
                                  fontes["publicacao.csv"], hash_preparacao, hash_lote, fontes["politica.json"], arquivo_csv.name)
        fontes["manifesto_decisoes.json"] = _hash(m_decisoes_bytes)
    # Nenhum sorteio ou produto aparece antes da validação integral das decisões.
    _validar_estabilidade(hashes)
    estratos, selecionados, publicadas = _selecionar(ids, m_lote["desenvolvimento_ids"], por_id_decisoes)
    por_id_questoes = {questao["id"]: questao for questao in questoes}
    cegos = [{campo: por_id_questoes[identificador][campo] for campo in ("id", "enunciado", "comando", "alternativas")}
             for identificador in selecionados]
    produtos = {
        "entradas_cegas.jsonl": "".join(_json(questao) + "\n" for questao in cegos).encode("utf-8"),
        "temas_preparados.json": produtos_preparacao["temas_preparados.json"],
        "manifesto_lote.json": lote_bytes,
        "politica.json": politica_bytes,
    }
    if m_decisoes_bytes is not None:
        produtos["manifesto_decisoes.json"] = m_decisoes_bytes
    manifesto = {
        "schema_version": 1, "procedimento": "auditoria-v1", "ids": selecionados,
        "total_questoes": len(ids), "total_publicadas": len(publicadas), "populacao_publicada_ids": publicadas,
        "desenvolvimento_ids": m_lote["desenvolvimento_ids"], "estratos": estratos,
        "semente": _SEMENTE, "maximo_amostra_restante": _MAXIMO_RESTANTE,
        "nivel_intervalo": m_politica["auditoria"]["nivel_intervalo"], "politica_versao": m_politica["versao"],
        "fontes_sha256": fontes, "preparacao_produtos_sha256": m_preparacao["produtos_sha256"],
        "lote_produtos_sha256": m_lote["produtos_sha256"],
        "produtos_sha256": {nome: _hash(conteudo) for nome, conteudo in produtos.items()},
        "data_exposure": "Todos os textos já foram inspecionados; casos de desenvolvimento separados; restante não é conjunto nunca visto.",
        "referencia_tipo": "Revisão por IA sem gabarito especialista; não equivale à precisão oficial.",
        "pacote_cego": "Somente entradas_cegas.jsonl e a taxonomia devem orientar a revisão inicial; decisões e trilha não entram no JSONL.",
        "limites": ["O CSV é validado estruturalmente; não contém todos os sinais necessários para reexecutar a política.",
                    "Congelamento vinculado aos hashes; alterações de decisões ou política exigem nova versão de auditoria.",
                    "Conhecer o modelo ou concordar com ele não fornece referência especialista."],
    }
    produtos["manifesto_auditoria.json"] = (_json(manifesto, indentar=True) + "\n").encode("utf-8")
    if any((saida / nome).resolve() in hashes for nome in produtos):
        raise ValueError("Um produto da auditoria coincide com uma fonte.")
    _validar_estabilidade(hashes)
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".auditoria-", dir=saida) as temporaria:
        pasta = Path(temporaria).resolve()
        if not pasta.is_relative_to(saida):
            raise ValueError("Pasta temporária fora do destino validado.")
        for nome, conteudo in produtos.items():
            (pasta / nome).write_bytes(conteudo)
        _validar_estabilidade(hashes)
        for nome in produtos:
            os.replace(pasta / nome, saida / nome)
    return manifesto


def _carregar_auditoria(preparacao: Path, auditoria: Path, decisoes: Path) -> tuple[dict, dict, dict, dict, dict[Path, str]]:
    """Revalida o pacote portátil para a avaliação, sem depender de recibos.

    Os snapshots do lote e da política permitem recompor a amostra; os hashes
    devolvidos correspondem a arquivos lidos e podem ser rechecadados ao gravar.
    """
    preparacao, auditoria = Path(preparacao).resolve(), Path(auditoria).resolve()
    hashes: dict[Path, str] = {}
    m_preparacao, produtos_preparacao, hash_preparacao, questoes, temas = _preparacao(preparacao, hashes)
    ids = [questao["id"] for questao in questoes]
    manifesto = _ler_json(_ler(auditoria / "manifesto_auditoria.json", hashes).decode("utf-8-sig"))
    if (
        not isinstance(manifesto, dict) or type(manifesto.get("schema_version")) is not int
        or manifesto["schema_version"] != 1 or manifesto.get("procedimento") != "auditoria-v1"
    ):
        raise ValueError("Manifesto da auditoria inválido ou não suportado.")
    produtos = _produtos(auditoria, manifesto.get("produtos_sha256"), hashes)
    if not {"entradas_cegas.jsonl", "temas_preparados.json", "manifesto_lote.json", "politica.json"}.issubset(produtos):
        raise ValueError("Pacote da auditoria sem todos os produtos obrigatórios.")
    fontes = manifesto.get("fontes_sha256")
    if not isinstance(fontes, dict) or fontes.get("manifesto.json") != hash_preparacao:
        raise ValueError("Auditoria e preparação não têm o mesmo manifesto.")
    if manifesto.get("preparacao_produtos_sha256") != m_preparacao["produtos_sha256"]:
        raise ValueError("Hashes de preparação divergentes na auditoria.")
    if produtos["temas_preparados.json"] != produtos_preparacao["temas_preparados.json"]:
        raise ValueError("Taxonomia do pacote cego difere da preparação.")
    for nome in ("manifesto_lote.json", "politica.json"):
        if fontes.get(nome) != _hash(produtos[nome]):
            raise ValueError("Snapshot não corresponde ao hash da fonte congelada.")
    m_lote = _validar_lote(_ler_json(produtos["manifesto_lote.json"].decode("utf-8-sig")), ids,
                           hash_preparacao, m_preparacao["produtos_sha256"])
    if manifesto.get("lote_produtos_sha256") != m_lote.get("produtos_sha256"):
        raise ValueError("Hashes do lote divergentes na auditoria.")
    m_politica = _validar_politica(_ler_json(produtos["politica.json"].decode("utf-8-sig")))
    por_id_decisoes, csv_bytes, manifesto_decisoes_bytes, arquivo_csv = _carregar_decisoes(Path(decisoes), ids, temas, hashes)
    if fontes.get("publicacao.csv") != _hash(csv_bytes):
        raise ValueError("As decisões mudaram após o congelamento da auditoria.")
    if "manifesto_decisoes.json" in produtos:
        congelado = produtos["manifesto_decisoes.json"]
        if fontes.get("manifesto_decisoes.json") != _hash(congelado):
            raise ValueError("Hash do manifesto das decisões divergente.")
        if manifesto_decisoes_bytes is not None and congelado != manifesto_decisoes_bytes:
            raise ValueError("Manifesto das decisões mudou após o congelamento.")
        _validar_manifesto_decisoes(_ler_json(congelado.decode("utf-8-sig")), por_id_decisoes,
                                  fontes["publicacao.csv"], hash_preparacao, fontes["manifesto_lote.json"], fontes["politica.json"], arquivo_csv.name)
    elif fontes.get("manifesto_decisoes.json") is not None:
        raise ValueError("Snapshot do manifesto das decisões ausente.")
    estratos, selecionados, publicadas = _selecionar(ids, m_lote["desenvolvimento_ids"], por_id_decisoes)
    esperados = {"estratos": estratos, "ids": selecionados, "populacao_publicada_ids": publicadas,
                 "total_questoes": len(ids), "total_publicadas": len(publicadas),
                 "desenvolvimento_ids": m_lote["desenvolvimento_ids"], "semente": _SEMENTE,
                 "maximo_amostra_restante": _MAXIMO_RESTANTE, "politica_versao": m_politica["versao"],
                 "nivel_intervalo": m_politica["auditoria"]["nivel_intervalo"]}
    if any(manifesto.get(campo) != valor for campo, valor in esperados.items()):
        raise ValueError("Estratos, seleção ou parâmetros divergem do sorteio congelado.")
    cegos = [_ler_json(linha) for linha in produtos["entradas_cegas.jsonl"].decode("utf-8-sig").split("\n") if linha.strip()]
    por_id_questoes = {questao["id"]: questao for questao in questoes}
    esperados_cegos = [{campo: por_id_questoes[identificador][campo] for campo in ("id", "enunciado", "comando", "alternativas")}
                       for identificador in selecionados]
    if cegos != esperados_cegos:
        raise ValueError("Conteúdo cego contém campos inesperados ou diverge das questões selecionadas.")
    _validar_estabilidade(hashes)
    return manifesto, temas, por_id_questoes, por_id_decisoes, hashes
