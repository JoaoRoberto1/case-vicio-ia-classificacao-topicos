"""Prepara casos e contratos de um piloto, sem chamar modelos ou publicar questões."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
from string import Template
import tempfile


_RAIZ = Path(__file__).resolve().parents[1]
_PROMPT = _RAIZ / "prompts" / "classificacao_v1.txt"
_VERSAO_PROMPT = "classificacao-v1"
_PRODUTOS_OBRIGATORIOS = {"questoes_preparadas.jsonl", "temas_preparados.json"}
_DELIBERADOS = {
    "Q0020": "Questão ampla: verificar mistura de conhecimentos e justificativa do tema central.",
    "Q0036": "Caso deliberado para examinar correspondência entre conteúdo e árvore.",
    "Q0078": "Texto com degradação observada: verificar limites sem reconstruir OCR.",
    "Q0099": "Alternativas com configuração do Word removida: verificar conteúdo preservado.",
    "Q0107": "Conhecimento substantivo está no comando e precisa participar da análise.",
    "Q0137": "Metadados de origem potencialmente incompatíveis com o conteúdo.",
    "Q0142": "Caso deliberado para examinar delimitação temática e temas concorrentes.",
    "Q0219": "Referência a situação hipotética possivelmente ausente: verificar necessidade de revisão.",
    "Q0239": "Enunciado genérico: conhecimento cobrado aparece nas alternativas.",
    "Q0284": "Caso deliberado para examinar abrangência temática das alternativas.",
}


def _hash(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _json(objeto: object, *, indentar: bool = False) -> str:
    return json.dumps(objeto, ensure_ascii=False, sort_keys=True, indent=2 if indentar else None)


def _objeto_sem_duplicatas(pares: list[tuple]) -> dict:
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError(f"Chave JSON duplicada: {chave!r}.")
        resultado[chave] = valor
    return resultado


def _ler_json(conteudo: str) -> object:
    try:
        return json.loads(conteudo, object_pairs_hook=_objeto_sem_duplicatas)
    except json.JSONDecodeError as erro:
        raise ValueError("JSON inválido nos artefatos da preparação.") from erro


def _validar_destino(preparacao: Path, saida: Path) -> tuple[Path, Path]:
    preparacao = preparacao.resolve()
    if any(parte.casefold() in {".git", "contexto_local"} for parte in saida.parts):
        raise ValueError("A pasta de saída está em uma área protegida.")
    if saida.is_symlink():
        raise ValueError("A pasta de saída não pode ser um link simbólico.")
    saida = saida.resolve()
    if any(parte.casefold() in {".git", "contexto_local"} for parte in saida.parts):
        raise ValueError("A pasta de saída está em uma área protegida.")
    if saida == _RAIZ or saida in _RAIZ.parents:
        raise ValueError("A saída não pode ser a raiz dos materiais nem um ancestral dela.")
    for nome in ("classificacao_topicos", "tests", "docs", "prompts"):
        protegida = (_RAIZ / nome).resolve()
        if saida == protegida or protegida in saida.parents:
            raise ValueError(f"A pasta {nome} é protegida e não pode receber produtos.")
    if saida == preparacao or preparacao in saida.parents or saida in preparacao.parents:
        raise ValueError("A saída deve ser separada da pasta de preparação e de seus ancestrais.")
    if saida.exists() and not saida.is_dir():
        raise ValueError("A saída deve ser uma pasta.")
    for nome in ("entradas.jsonl", "manifesto_piloto.json"):
        produto = saida / nome
        if produto.is_symlink() or (produto.exists() and not produto.is_file()):
            raise ValueError(f"Destino de produto não é um arquivo comum: {nome}.")
    return preparacao, saida


def _carregar_preparacao(preparacao: Path) -> tuple[dict, dict[str, bytes], str]:
    caminho_manifesto = preparacao / "manifesto.json"
    if caminho_manifesto.is_symlink() or not caminho_manifesto.is_file():
        raise ValueError("Manifesto da preparação ausente ou não é um arquivo comum.")
    manifesto_bytes = caminho_manifesto.read_bytes()
    manifesto = _ler_json(manifesto_bytes.decode("utf-8-sig"))
    if not isinstance(manifesto, dict) or manifesto.get("procedimento") != "preparacao-v1":
        raise ValueError("Manifesto não corresponde à preparação-v1.")
    if type(manifesto.get("schema_version")) is not int or manifesto["schema_version"] != 1:
        raise ValueError("Versão do manifesto de preparação não suportada.")
    hashes = manifesto.get("produtos_sha256")
    if not isinstance(hashes, dict) or not _PRODUTOS_OBRIGATORIOS.issubset(hashes):
        raise ValueError("Manifesto sem os hashes dos produtos obrigatórios.")
    conteudos = {}
    for nome, esperado in sorted(hashes.items()):
        if (
            not isinstance(nome, str) or not nome or Path(nome).name != nome
            or nome in {".", ".."} or ":" in nome or "/" in nome or "\\" in nome
        ):
            raise ValueError("Nome de produto inseguro no manifesto da preparação.")
        if not isinstance(esperado, str) or not re.fullmatch(r"[0-9a-f]{64}", esperado):
            raise ValueError(f"Hash SHA-256 inválido no manifesto: {nome}.")
        caminho = preparacao / nome
        if caminho.is_symlink() or not caminho.is_file():
            raise ValueError(f"Produto de preparação ausente ou não é arquivo comum: {nome}.")
        conteudo = caminho.read_bytes()
        if _hash(conteudo) != esperado:
            raise ValueError(f"Hash divergente no produto de preparação: {nome}.")
        conteudos[nome] = conteudo
    return manifesto, conteudos, _hash(manifesto_bytes)


def _carregar_questoes(conteudo: bytes) -> list[dict]:
    questoes = []
    ids = set()
    # LF separa registros; U+2028/U+0085 podem fazer parte do conteúdo JSON.
    for linha in conteudo.decode("utf-8-sig").split("\n"):
        if not linha.strip():
            continue
        questao = _ler_json(linha)
        if not isinstance(questao, dict):
            raise ValueError("Questão preparada deve ser um objeto JSON.")
        for campo in ("id", "enunciado", "comando", "disciplina_origem"):
            if not isinstance(questao.get(campo), str):
                raise ValueError(f"Questão preparada sem campo textual {campo}.")
        identificador = questao["id"]
        if not identificador.strip() or identificador != identificador.strip() or identificador in ids:
            raise ValueError("ID de questão preparado vazio, com espaços ou duplicado.")
        alternativas = questao.get("alternativas")
        if not isinstance(alternativas, dict) or len(alternativas) < 2 or any(
            not isinstance(k, str) or not k.strip() or not isinstance(v, str)
            for k, v in alternativas.items()
        ):
            raise ValueError(f"Alternativas inválidas em {identificador}.")
        ids.add(identificador)
        questoes.append(questao)
    if not questoes:
        raise ValueError("Nenhuma questão preparada disponível.")
    return questoes


def _catalogo(conteudo: bytes) -> tuple[list[dict], list[str]]:
    temas = _ler_json(conteudo.decode("utf-8-sig"))
    if not isinstance(temas, list) or not temas:
        raise ValueError("Os temas preparados devem formar uma lista não vazia.")
    ativos, omitidas, ids = [], [], set()
    for tema in temas:
        if not isinstance(tema, dict) or any(
            not isinstance(tema.get(campo), str)
            for campo in ("tema_id", "parent_id", "nivel", "titulo", "caminho", "descricao", "status")
        ):
            raise ValueError("Esquema inválido nos temas preparados.")
        tema_id = tema["tema_id"]
        if not tema_id.strip() or tema_id != tema_id.strip() or tema_id in ids:
            raise ValueError("ID de tema preparado vazio, com espaços ou duplicado.")
        if tema["status"] not in {"active", "inactive"}:
            raise ValueError(f"Status inválido no tema {tema_id}.")
        ids.add(tema_id)
        if tema["status"] != "active":
            continue
        registro = {
            "id": tema_id, "parent": tema["parent_id"], "nivel": tema["nivel"],
            "titulo": tema["titulo"], "caminho": tema.get("caminho_calculado", tema["caminho"]),
        }
        descricao = tema["descricao"].strip()
        if descricao.startswith(("Disciplina (root).", "Subtema de ")):
            omitidas.append(tema_id)
        elif descricao:
            registro["descricao"] = tema["descricao"]
        ativos.append(registro)
    if not ativos:
        raise ValueError("Nenhum tema ativo disponível para o catálogo.")
    return sorted(ativos, key=lambda tema: tema["id"]), sorted(omitidas)


def _selecionar(questoes: list[dict], tamanho: int, semente: int) -> tuple[list[dict], dict]:
    if type(tamanho) is not int or tamanho < 1 or tamanho > len(questoes):
        raise ValueError("Tamanho do piloto deve ser inteiro positivo e caber no conjunto.")
    if type(semente) is not int:
        raise ValueError("A semente deve ser um número inteiro.")
    por_id = {q["id"]: q for q in questoes}
    selecionados = [por_id[identificador] for identificador in _DELIBERADOS if identificador in por_id]
    if tamanho < len(selecionados):
        raise ValueError("Tamanho insuficiente para incluir todos os casos deliberados presentes.")
    motivos = {q["id"]: ["seleção deliberada", _DELIBERADOS[q["id"]]] for q in selecionados}
    contagem_disciplina = Counter(q["disciplina_origem"] for q in selecionados)
    contagem_alternativas = Counter(len(q["alternativas"]) for q in selecionados)
    contagem_par = Counter((q["disciplina_origem"], len(q["alternativas"])) for q in selecionados)
    pendentes = [q for q in questoes if q["id"] not in motivos]

    def prioridade(questao: dict) -> tuple:
        disciplina, alternativas = questao["disciplina_origem"], len(questao["alternativas"])
        desempate = _hash(f"{semente}:{questao['id']}".encode("utf-8"))
        return (
            contagem_disciplina[disciplina], contagem_alternativas[alternativas],
            contagem_par[(disciplina, alternativas)], desempate, questao["id"],
        )

    while len(selecionados) < tamanho:
        questao = min(pendentes, key=prioridade)
        pendentes.remove(questao)
        selecionados.append(questao)
        disciplina, alternativas = questao["disciplina_origem"], len(questao["alternativas"])
        motivos[questao["id"]] = [
            "complemento determinístico por diversidade estrutural",
            f"disciplina_origem={disciplina!r}; quantidade_alternativas={alternativas}",
            "origem usada somente para diversificar, nunca como rótulo de referência",
        ]
        contagem_disciplina[disciplina] += 1
        contagem_alternativas[alternativas] += 1
        contagem_par[(disciplina, alternativas)] += 1
    return selecionados, motivos


def esquema_resposta() -> dict:
    """Contrato sem enumeração da taxonomia; validade de IDs é verificada localmente."""
    lista_ids = {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True}
    propriedades = {
        "id": {"type": "string", "minLength": 1},
        "tema_central_id": {"type": "string"},
        "extras_ids": dict(lista_ids),
        "temas_alternativos": dict(lista_ids),
        "sem_tema": {"type": "boolean"},
        "confianca_autodeclarada": {"type": "number", "minimum": 0, "maximum": 1},
        "motivo": {"type": "string", "minLength": 1},
        "evidencia": {"type": "string", "minLength": 1},
        "requer_revisao": {"type": "boolean"},
    }
    return {
        "type": "object", "properties": propriedades,
        "required": list(propriedades), "additionalProperties": False,
    }


def validar_resposta(resposta: dict, questao_id: str, temas_por_id: dict) -> dict:
    """Valida somente o contrato técnico; não atesta correção temática ou precisão.

    A presença literal de evidencia na questão é responsabilidade do executor,
    que possui o texto da pergunta. Aqui se exige uma string não vazia. Um ID
    inválido gera erro; não é convertido em sem_tema nem em tema genérico.
    """
    if not isinstance(resposta, dict) or set(resposta) != set(esquema_resposta()["required"]):
        raise ValueError("Resposta com campos ausentes ou inesperados.")
    if not isinstance(questao_id, str) or not questao_id.strip() or resposta["id"] != questao_id:
        raise ValueError("ID da resposta não corresponde à questão solicitada.")
    for campo in ("id", "tema_central_id", "motivo", "evidencia"):
        if not isinstance(resposta[campo], str):
            raise ValueError(f"O campo {campo} deve ser texto.")
    for campo in ("motivo", "evidencia"):
        if not resposta[campo].strip():
            raise ValueError(f"O campo {campo} não pode ser vazio.")
    for campo in ("sem_tema", "requer_revisao"):
        if type(resposta[campo]) is not bool:
            raise ValueError(f"O campo {campo} deve ser booleano.")
    confianca = resposta["confianca_autodeclarada"]
    if type(confianca) not in {int, float} or not 0 <= confianca <= 1 or not math.isfinite(confianca):
        raise ValueError("Confiança autodeclarada deve ser número finito entre 0 e 1.")
    for campo in ("extras_ids", "temas_alternativos"):
        valores = resposta[campo]
        if not isinstance(valores, list) or any(not isinstance(v, str) or not v.strip() for v in valores):
            raise ValueError(f"O campo {campo} deve ser uma lista de IDs textuais não vazios.")
        if len(valores) != len(set(valores)):
            raise ValueError(f"IDs duplicados em {campo}.")
    central = resposta["tema_central_id"]
    if resposta["sem_tema"]:
        if central != "" or resposta["extras_ids"]:
            raise ValueError("sem_tema exige tema_central_id vazio e extras_ids vazio.")
    elif not central.strip():
        raise ValueError("Resposta com tema deve informar tema_central_id.")
    ids = ([central] if central else []) + resposta["extras_ids"] + resposta["temas_alternativos"]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs repetidos entre tema central, extras e temas alternativos.")
    for identificador in ids:
        tema = temas_por_id.get(identificador)
        if not isinstance(tema, dict) or tema.get("status") != "active":
            raise ValueError(f"ID de tema inexistente ou inativo: {identificador!r}.")
    # Nova cópia serializável, sem acrescentar autorização de publicação.
    return {**resposta, "extras_ids": list(resposta["extras_ids"]),
            "temas_alternativos": list(resposta["temas_alternativos"])}


def preparar_piloto(
    preparacao: Path, saida: Path, tamanho: int = 20, semente: int = 20261014,
    *, prompt_path: Path | None = None, prompt_version: str = "classificacao-v1",
) -> dict:
    """Gera prompts completos e manifesto reproduzível de desenvolvimento.

    O restante não é um conjunto nunca visto: todos os dados foram inspecionados.
    A seleção deliberada e a diversidade impedem usar este piloto como amostra
    representativa para estimar precisão ou demonstrar a meta de 95%.
    Variantes recebem seu próprio caminho e identificador de versão; os bytes
    do template efetivamente usado determinam o hash registrado no manifesto.
    """
    if not isinstance(prompt_version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", prompt_version):
        raise ValueError("Versão do prompt deve ser um identificador simples de até 80 caracteres, sem espaços ou barras.")
    preparacao, saida = _validar_destino(Path(preparacao), Path(saida))
    manifesto_preparacao, conteudos, hash_preparacao = _carregar_preparacao(preparacao)
    questoes = _carregar_questoes(conteudos["questoes_preparadas.jsonl"])
    catalogo, descricoes_omitidas = _catalogo(conteudos["temas_preparados.json"])
    selecionados, motivos = _selecionar(questoes, tamanho, semente)
    caminho_prompt = _PROMPT if prompt_path is None else Path(prompt_path)
    if caminho_prompt.is_symlink() or not caminho_prompt.is_file():
        raise ValueError("Template do prompt ausente ou não é arquivo comum.")
    prompt_bytes = caminho_prompt.read_bytes()
    try:
        template = Template(prompt_bytes.decode("utf-8-sig"))
    except UnicodeDecodeError as erro:
        raise ValueError("Template do prompt deve estar codificado em UTF-8.") from erro
    if not template.is_valid() or set(template.get_identifiers()) != {"QUESTAO_JSON", "CATALOGO_JSONL", "ESQUEMA_JSON"}:
        raise ValueError("Template deve conter somente os marcadores QUESTAO_JSON, CATALOGO_JSONL e ESQUEMA_JSON, incluindo os três.")
    catalogo_texto = "\n".join(_json(tema) for tema in catalogo)
    esquema_texto = _json(esquema_resposta())
    entradas = []
    for questao in selecionados:
        # Campos explícitos: nenhuma origem ou sugestão histórica entra no prompt.
        dados_questao = {campo: questao[campo] for campo in ("id", "enunciado", "comando", "alternativas")}
        prompt = template.substitute(
            QUESTAO_JSON=_json(dados_questao), CATALOGO_JSONL=catalogo_texto, ESQUEMA_JSON=esquema_texto
        )
        entradas.append({"id": questao["id"], "prompt": prompt, "sha256_prompt": _hash(prompt.encode("utf-8"))})
    entradas_bytes = ("".join(_json(entrada) + "\n" for entrada in entradas)).encode("utf-8")
    ids = [questao["id"] for questao in selecionados]
    manifesto = {
        "schema_version": 1, "procedimento": "piloto-v1", "ids": ids, "motivos": motivos,
        "seed": semente, "tamanho": len(ids), "total_questoes_disponiveis": len(questoes),
        "prompt_version": prompt_version, "prompt_sha256": _hash(prompt_bytes),
        "preparacao_sha256": hash_preparacao,
        "preparacao_produtos_sha256": manifesto_preparacao["produtos_sha256"],
        "produtos_sha256": {"entradas.jsonl": _hash(entradas_bytes)},
        "total_temas_ativos_no_prompt": len(catalogo),
        "descricoes_metadados_omitidas_ids": descricoes_omitidas,
        "data_exposure": "conjunto já inspecionado; casos de desenvolvimento; não auditoria",
        "restante_ids": sorted(q["id"] for q in questoes if q["id"] not in motivos),
        "restante_uso": "Elegíveis à auditoria local futura; não são dados nunca vistos nem gabarito oficial.",
        "decisoes_protocolo": {
            "origem_no_prompt": False,
            "motivo_omissao_origem": "Hipótese inicial para reduzir ancoragem em classificações de origem possivelmente incorretas.",
            "uso_origem_selecao": "Diversificar disciplinas de origem e quantidades de alternativas; origem não é rótulo de referência.",
            "desempate_selecao": "Menor contagem de disciplina, de quantidade de alternativas e do par; desempate por SHA-256(semente:id).",
            "descricao_metadados": "Omitida somente do prompt quando começa por 'Disciplina (root).' ou 'Subtema de '.",
            "catalogo": "Todos os IDs ativos, preservando ramos e títulos repetidos.",
            "saida": "Sugestão de desenvolvimento; não autoriza publicar, revisar ou fora.",
            "confianca": "Autodeclarada, não calibrada; não constitui estimativa de precisão.",
        },
    }
    produtos = {
        "entradas.jsonl": entradas_bytes,
        "manifesto_piloto.json": (_json(manifesto, indentar=True) + "\n").encode("utf-8"),
    }
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".piloto-", dir=saida) as temporaria:
        pasta = Path(temporaria).resolve()
        if not pasta.is_relative_to(saida):
            raise ValueError("Pasta temporária fora do destino validado.")
        for nome, conteudo in produtos.items():
            (pasta / nome).write_bytes(conteudo)
        # Manifesto por último: não deixar a execução antiga parecer completa.
        (saida / "manifesto_piloto.json").unlink(missing_ok=True)
        for nome in produtos:
            os.replace(pasta / nome, saida / nome)
    return manifesto
