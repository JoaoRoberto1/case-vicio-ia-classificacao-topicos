"""Prepara todas as questões sem redefinir a amostra de desenvolvimento."""

from __future__ import annotations

import os
from pathlib import Path
import re
from string import Template
import tempfile

from .piloto import (
    _carregar_preparacao, _carregar_questoes, _catalogo, _hash, _json,
    _ler_json, _validar_destino, esquema_resposta,
)


def _ler_comum(caminho: Path) -> bytes:
    if caminho.is_symlink() or not caminho.is_file():
        raise ValueError(f"Artefato ausente ou não é arquivo comum: {caminho.name}.")
    return caminho.read_bytes()


def _ids_validos(ids: object, nome: str) -> list[str]:
    if not isinstance(ids, list) or any(
        not isinstance(identificador, str) or not identificador.strip()
        or identificador != identificador.strip() for identificador in ids
    ) or len(ids) != len(set(ids)):
        raise ValueError(f"Lista de IDs inválida ou duplicada: {nome}.")
    return ids


def _carregar_desenvolvimento(
    pasta: Path, manifesto_preparacao: dict, hash_preparacao: str, ids_questoes: list[str]
) -> tuple[dict, str]:
    manifesto_bytes = _ler_comum(pasta / "manifesto_piloto.json")
    manifesto = _ler_json(manifesto_bytes.decode("utf-8-sig"))
    if not isinstance(manifesto, dict) or manifesto.get("procedimento") != "piloto-v1":
        raise ValueError("Manifesto de desenvolvimento deve corresponder a piloto-v1.")
    if type(manifesto.get("schema_version")) is not int or manifesto["schema_version"] != 1:
        raise ValueError("Versão de manifesto do desenvolvimento não suportada.")
    if (
        manifesto.get("preparacao_sha256") != hash_preparacao
        or manifesto.get("preparacao_produtos_sha256") != manifesto_preparacao["produtos_sha256"]
    ):
        raise ValueError("Piloto de desenvolvimento pertence a outra preparação ou seus hashes divergem.")
    ids = _ids_validos(manifesto.get("ids"), "desenvolvimento")
    if not ids or not set(ids).issubset(ids_questoes):
        raise ValueError("O desenvolvimento deve ser um subconjunto não vazio das questões preparadas.")
    if type(manifesto.get("tamanho")) is not int or manifesto["tamanho"] != len(ids):
        raise ValueError("Tamanho do desenvolvimento incompatível com seus IDs.")
    if (
        type(manifesto.get("total_questoes_disponiveis")) is not int
        or manifesto["total_questoes_disponiveis"] != len(ids_questoes)
    ):
        raise ValueError("Total de questões do desenvolvimento difere da preparação.")
    restantes = _ids_validos(manifesto.get("restante_ids"), "restante do piloto")
    if set(restantes) != set(ids_questoes) - set(ids):
        raise ValueError("A partição de desenvolvimento e restante não corresponde à preparação.")
    hashes = manifesto.get("produtos_sha256")
    if not isinstance(hashes, dict) or "entradas.jsonl" not in hashes:
        raise ValueError("Manifesto do desenvolvimento sem hash das entradas.")
    produtos = {}
    for nome, esperado in sorted(hashes.items()):
        if not isinstance(nome, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", nome) or nome in {".", ".."}:
            raise ValueError("Nome de produto inseguro no manifesto do desenvolvimento.")
        if not isinstance(esperado, str) or not re.fullmatch(r"[a-f0-9]{64}", esperado):
            raise ValueError("Hash inválido no manifesto do desenvolvimento.")
        conteudo = _ler_comum(pasta / nome)
        if _hash(conteudo) != esperado:
            raise ValueError(f"Hash divergente no produto do desenvolvimento: {nome}.")
        produtos[nome] = conteudo
    entradas = []
    for linha in produtos["entradas.jsonl"].decode("utf-8-sig").split("\n"):
        if not linha.strip():
            continue
        entrada = _ler_json(linha)
        if not isinstance(entrada, dict) or set(entrada) != {"id", "prompt", "sha256_prompt"}:
            raise ValueError("Entrada de desenvolvimento com esquema inválido.")
        if not isinstance(entrada["prompt"], str) or not entrada["prompt"].strip():
            raise ValueError("Prompt vazio ou inválido no desenvolvimento.")
        if entrada["sha256_prompt"] != _hash(entrada["prompt"].encode("utf-8")):
            raise ValueError("Hash individual de prompt divergente no desenvolvimento.")
        entradas.append(entrada)
    if [entrada["id"] for entrada in entradas] != ids:
        raise ValueError("IDs ou ordem das entradas divergem do manifesto de desenvolvimento.")
    if not isinstance(manifesto.get("prompt_version"), str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", manifesto["prompt_version"]
    ):
        raise ValueError("Versão do prompt de desenvolvimento inválida.")
    if not isinstance(manifesto.get("prompt_sha256"), str) or not re.fullmatch(
        r"[a-f0-9]{64}", manifesto["prompt_sha256"]
    ):
        raise ValueError("Hash do template de desenvolvimento inválido.")
    return manifesto, _hash(manifesto_bytes)


def preparar_lote(
    preparacao: Path, piloto_desenvolvimento: Path, saida: Path,
    *, prompt_path: Path, prompt_version: str,
) -> dict:
    """Gera entradas para todo o lote e preserva o subconjunto de desenvolvimento.

    Processar uma questão não a torna caso de ajuste. O manifesto identifica a
    exposição prévia de todo o conjunto e não trata o restante como nunca visto.
    Nenhum modelo é chamado e nenhuma decisão de publicação é produzida.
    """
    if not isinstance(prompt_version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", prompt_version):
        raise ValueError("Versão do prompt deve ser um identificador simples de até 80 caracteres.")
    preparacao, saida = _validar_destino(Path(preparacao), Path(saida))
    piloto_desenvolvimento = Path(piloto_desenvolvimento).resolve()
    if (
        saida == piloto_desenvolvimento or piloto_desenvolvimento in saida.parents
        or saida in piloto_desenvolvimento.parents
    ):
        raise ValueError("A saída do lote deve ser separada da pasta do piloto de desenvolvimento.")
    if (saida / "manifesto_piloto.json").exists():
        raise ValueError("A saída contém um piloto; use uma pasta separada para o lote.")
    destino_manifesto = saida / "manifesto_lote.json"
    if destino_manifesto.is_symlink() or (destino_manifesto.exists() and not destino_manifesto.is_file()):
        raise ValueError("Destino do manifesto do lote não é arquivo comum.")
    caminho_prompt = Path(prompt_path)
    if caminho_prompt.resolve() in {saida / "entradas.jsonl", destino_manifesto}:
        raise ValueError("O template do prompt não pode coincidir com um produto de saída.")

    manifesto_preparacao, conteudos, hash_preparacao = _carregar_preparacao(preparacao)
    questoes = _carregar_questoes(conteudos["questoes_preparadas.jsonl"])
    ids = [questao["id"] for questao in questoes]
    manifesto_desenvolvimento, hash_desenvolvimento = _carregar_desenvolvimento(
        piloto_desenvolvimento, manifesto_preparacao, hash_preparacao, ids
    )
    catalogo, descricoes_omitidas = _catalogo(conteudos["temas_preparados.json"])
    prompt_bytes = _ler_comum(caminho_prompt)
    try:
        template = Template(prompt_bytes.decode("utf-8-sig"))
    except UnicodeDecodeError as erro:
        raise ValueError("Template do prompt deve estar codificado em UTF-8.") from erro
    if not template.is_valid() or set(template.get_identifiers()) != {"QUESTAO_JSON", "CATALOGO_JSONL", "ESQUEMA_JSON"}:
        raise ValueError("Template deve conter somente os marcadores QUESTAO_JSON, CATALOGO_JSONL e ESQUEMA_JSON, incluindo os três.")
    catalogo_texto = "\n".join(_json(tema) for tema in catalogo)
    esquema_texto = _json(esquema_resposta())
    entradas = []
    for questao in questoes:
        dados_questao = {campo: questao[campo] for campo in ("id", "enunciado", "comando", "alternativas")}
        prompt = template.substitute(
            QUESTAO_JSON=_json(dados_questao), CATALOGO_JSONL=catalogo_texto, ESQUEMA_JSON=esquema_texto
        )
        entradas.append({"id": questao["id"], "prompt": prompt, "sha256_prompt": _hash(prompt.encode("utf-8"))})
    entradas_bytes = "".join(_json(entrada) + "\n" for entrada in entradas).encode("utf-8")
    desenvolvimento_ids = list(manifesto_desenvolvimento["ids"])
    desenvolvimento_set = set(desenvolvimento_ids)
    manifesto = {
        "schema_version": 1, "procedimento": "lote-v1", "ids": ids,
        "tamanho": len(ids), "total_questoes_disponiveis": len(ids),
        "desenvolvimento_ids": desenvolvimento_ids,
        "restante_ids": [identificador for identificador in ids if identificador not in desenvolvimento_set],
        "desenvolvimento_manifesto_sha256": hash_desenvolvimento,
        "desenvolvimento_produtos_sha256": manifesto_desenvolvimento["produtos_sha256"],
        "desenvolvimento_prompt_version": manifesto_desenvolvimento["prompt_version"],
        "desenvolvimento_prompt_sha256": manifesto_desenvolvimento["prompt_sha256"],
        "preparacao_sha256": hash_preparacao,
        "preparacao_produtos_sha256": manifesto_preparacao["produtos_sha256"],
        "produtos_sha256": {"entradas.jsonl": _hash(entradas_bytes)},
        "prompt_version": prompt_version, "prompt_sha256": _hash(prompt_bytes),
        "total_temas_ativos_no_prompt": len(catalogo),
        "descricoes_metadados_omitidas_ids": descricoes_omitidas,
        "data_exposure": "Todos os dados já foram inspecionados; processar o lote completo não cria um novo conjunto de desenvolvimento.",
        "restante_uso": "Restante separado dos casos de desenvolvimento; elegível à auditoria local futura, não é conjunto nunca visto nem gabarito oficial.",
        "decisoes_protocolo": {
            "ordem": "Todos os IDs, exatamente na ordem do arquivo de questões preparadas.",
            "desenvolvimento": "Lista congelada do piloto informado; não ampliada pela execução do lote.",
            "origem_no_prompt": False,
            "catalogo": "Todos os temas ativos, com o mesmo catálogo e esquema usados pelo piloto.",
            "descricao_metadados": "Omitida somente do prompt quando começa por 'Disciplina (root).' ou 'Subtema de '.",
            "saida": "Entradas para classificação; não autoriza publicação nem constitui avaliação de precisão.",
        },
    }
    produtos = {
        "entradas.jsonl": entradas_bytes,
        "manifesto_lote.json": (_json(manifesto, indentar=True) + "\n").encode("utf-8"),
    }
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".lote-", dir=saida) as temporaria:
        pasta = Path(temporaria).resolve()
        if not pasta.is_relative_to(saida):
            raise ValueError("Pasta temporária fora do destino validado.")
        for nome, conteudo in produtos.items():
            (pasta / nome).write_bytes(conteudo)
        destino_manifesto.unlink(missing_ok=True)
        for nome in produtos:
            os.replace(pasta / nome, saida / nome)
    return manifesto
