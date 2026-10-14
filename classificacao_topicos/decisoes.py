"""Aplicação offline da política congelada e exportação com rastreabilidade.

Nenhuma decisão fora é inferida automaticamente. A confiança em publicar/revisar
continua autodeclarada; em fora, zero é uma sentinela não aplicável documentada.
"""

from __future__ import annotations

from collections import Counter
import csv
import io
import json
import os
from pathlib import Path
import re
import tempfile

from .analise_piloto import _tentativas
from .execucao import (
    _canonico, _hash_bytes, _json, _ler, _validar_cache, _validar_entradas, _validar_saida,
)
from .piloto import esquema_resposta
from .politica import aplicar_politica


_COLUNAS = ("id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo")
_PRODUTOS = {"trilha_decisoes.jsonl", "pendentes_fora.jsonl", "publicacao.csv", "manifesto_decisoes.json"}
_REGRAS_V1 = {
    "modelo_requer_revisao", "confianca_abaixo_limiar", "candidatos_concorrentes",
    "central_disciplina_nivel_0", "central_em_colisao_de_ramos", "extras_acima_limite",
}


def _carregar_politica(caminho: Path, manifesto_lote: dict, preparacao: Path,
                       raiz: Path) -> tuple[dict, Path, dict]:
    conteudo = _ler(caminho)
    politica = _json(conteudo)
    if not isinstance(politica, dict) or type(politica.get("schema_version")) is not int:
        raise ValueError("Política deve ser um objeto com versão de esquema inteira.")
    if politica["schema_version"] != 1 or politica.get("versao") != "politica-v1":
        raise ValueError("Versão da política não suportada.")
    modelo = politica.get("modelo")
    if not isinstance(modelo, str) or not re.fullmatch(r"gemini-[a-z0-9]+(?:[.-][a-z0-9]+)*", modelo):
        raise ValueError("Modelo inválido na política.")
    if (not isinstance(politica.get("prompt_version"), str) or not politica["prompt_version"]
            or politica["prompt_version"] != manifesto_lote.get("prompt_version")):
        raise ValueError("A versão do prompt do lote diverge da política.")
    regras = politica.get("revisar_quando")
    if (not isinstance(regras, list) or any(not isinstance(r, str) for r in regras)
            or len(regras) != len(_REGRAS_V1) or set(regras) != _REGRAS_V1):
        raise ValueError("As regras declaradas divergem da política-v1 implementada.")
    ids = politica.get("ids_ambiguos")
    if (not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("IDs ambíguos inválidos na política.")
    if "confianca_minima" not in politica or "max_extras_publicar" not in politica:
        raise ValueError("Política sem parâmetros operacionais explícitos.")
    fonte = politica.get("ambiguidades_fonte")
    if not isinstance(fonte, str) or not fonte:
        raise ValueError("Política sem fonte de ambiguidades.")
    relativo = Path(fonte)
    if relativo.is_absolute() or relativo.drive or ".." in relativo.parts:
        raise ValueError("A fonte de ambiguidades deve ser relativa à raiz dos materiais.")
    caminho_ambiguidades = raiz / relativo
    ambiguidades_bytes = _ler(caminho_ambiguidades)
    hash_ambiguidades = _hash_bytes(ambiguidades_bytes)
    if politica.get("ambiguidades_sha256") != hash_ambiguidades:
        raise ValueError("Hash da fonte de ambiguidades diverge da política.")
    ambiguidades = _json(ambiguidades_bytes)
    if (not isinstance(ambiguidades, dict) or type(ambiguidades.get("schema_version")) is not int
            or ambiguidades["schema_version"] != 1):
        raise ValueError("Fonte de ambiguidades inválida.")
    if ambiguidades.get("fonte_sha256") != _hash_bytes(_ler(preparacao / "temas_preparados.json")):
        raise ValueError("As ambiguidades foram definidas sobre outra taxonomia.")
    ids_fonte = set()
    for campo in ("grupos_exatos", "grupos_semanticos_possiveis"):
        grupos = ambiguidades.get(campo)
        if not isinstance(grupos, list):
            raise ValueError("Fonte de ambiguidades sem listas de grupos.")
        for grupo in grupos:
            membros = grupo.get("ids") if isinstance(grupo, dict) else None
            if (not isinstance(membros, list) or not membros
                    or any(not isinstance(i, str) or not i for i in membros)
                    or len(membros) != len(set(membros))):
                raise ValueError("Grupo de ambiguidades contém IDs inválidos.")
            ids_fonte.update(membros)
    if set(ids) != ids_fonte:
        raise ValueError("IDs ambíguos da política divergem dos grupos assinados.")
    return politica, caminho_ambiguidades, {caminho: _hash_bytes(conteudo), caminho_ambiguidades: hash_ambiguidades}


def _carregar_confirmacoes(caminho: Path | None, candidatos: set[str]) -> tuple[dict, dict]:
    if caminho is None:
        return {}, {}
    conteudo = _ler(caminho)
    confirmacoes = {}
    campos = {"id", "sem_tema", "situacao", "justificativa", "responsavel", "tipo_referencia"}
    for linha in conteudo.decode("utf-8-sig").split("\n"):
        if not linha.strip():
            continue
        item = _json(linha)
        if not isinstance(item, dict) or set(item) != campos:
            raise ValueError("Confirmação fora contém campos ausentes ou inesperados.")
        identificador = item["id"]
        if not isinstance(identificador, str) or identificador not in candidatos:
            raise ValueError("Confirmação fora só pode referir um candidato sem tema deste lote.")
        if identificador in confirmacoes:
            raise ValueError("Confirmação fora duplicada.")
        if item["sem_tema"] is not True or item["situacao"] != "confirmado":
            raise ValueError("Confirmação fora exige sem_tema true e situação confirmado.")
        if not isinstance(item["tipo_referencia"], str) or item["tipo_referencia"] not in {"IA", "especialista"}:
            raise ValueError("Tipo de referência da confirmação deve ser IA ou especialista.")
        for campo in ("justificativa", "responsavel"):
            if not isinstance(item[campo], str) or not item[campo].strip():
                raise ValueError("Confirmação fora exige justificativa e responsável textuais não vazios.")
        confirmacoes[identificador] = item
    return confirmacoes, {caminho: _hash_bytes(conteudo)}


def _jsonl(linhas: list[dict]) -> bytes:
    return b"".join(_canonico(linha) + b"\n" for linha in linhas)


def preparar_decisoes(lote: Path, preparacao: Path, execucao: Path, politica: Path,
                      saida: Path, *, confirmacoes_fora: Path | None = None) -> dict:
    """Gera trilha completa; publica CSV somente com todas as decisões resolvidas.

    Exige sucesso técnico em todos os IDs preparados e confirmação explícita
    para cada sem_tema. Não acessa credenciais, redes ou modelos.
    """
    lote, preparacao, execucao = (Path(p).resolve() for p in (lote, preparacao, execucao))
    caminho_politica = Path(politica).absolute()
    caminho_confirmacoes = Path(confirmacoes_fora).absolute() if confirmacoes_fora is not None else None
    entradas, temas, questoes, hash_preparacao, raiz = _validar_entradas(
        lote, preparacao, procedimento_esperado="lote-v1")
    saida = _validar_saida(Path(saida), piloto=lote, preparacao=preparacao, raiz=raiz)
    if saida == execucao or saida in execucao.parents or execucao in saida.parents:
        raise ValueError("A saída de decisões deve ser separada dos recibos.")
    if not execucao.is_dir() or (execucao / ".execucao.lock").exists():
        raise ValueError("Pasta de recibos ausente ou execução ainda ativa.")
    manifesto_lote_bytes = _ler(lote / "manifesto_lote.json")
    manifesto_lote = _json(manifesto_lote_bytes)
    config, ambiguidades, hashes_fontes = _carregar_politica(
        caminho_politica, manifesto_lote, preparacao, raiz)
    hashes_fontes[lote / "manifesto_lote.json"] = _hash_bytes(manifesto_lote_bytes)
    hashes_fontes[preparacao / "manifesto.json"] = hash_preparacao
    for fonte in (caminho_politica, ambiguidades, caminho_confirmacoes):
        if fonte is not None and (saida == fonte.resolve() or saida in fonte.resolve().parents):
            raise ValueError("A saída de decisões não pode conter uma fonte de política ou confirmação.")
    permitidos = {e["id"] + ".json" for e in entradas}
    if {p.name for p in execucao.iterdir()} != permitidos:
        raise ValueError("É necessário um recibo para cada questão, sem arquivos extras ou IDs ausentes.")
    schema_hash = _hash_bytes(_canonico(esquema_resposta()))
    entradas_por_id = {e["id"]: e for e in entradas}
    registros, politicas, hashes_recibos = {}, {}, {}
    # A preparação preserva a ordem original, independentemente da ordem do lote.
    for identificador, questao in questoes.items():
        arquivo = execucao / (identificador + ".json")
        hash_recibo = _hash_bytes(_ler(arquivo))
        registro = _validar_cache(arquivo, entradas_por_id[identificador], config["modelo"],
                                  schema_hash, hash_preparacao, temas, questao)
        _tentativas(registro)
        if registro["status"] != "sucesso":
            raise ValueError("Todos os recibos devem ter sucesso técnico antes de preparar decisões.")
        registros[identificador] = registro
        hashes_recibos[arquivo.name] = hash_recibo
        hashes_fontes[arquivo] = hash_recibo
        politicas[identificador] = aplicar_politica(
            registro["sugestao"], temas, set(config["ids_ambiguos"]),
            confianca_minima=config["confianca_minima"], max_extras_publicar=config["max_extras_publicar"])
    candidatos = {i for i, r in politicas.items() if r["estado"] == "pendente_confirmacao_fora"}
    confirmacoes, hashes_confirmacoes = _carregar_confirmacoes(caminho_confirmacoes, candidatos)
    hashes_fontes.update(hashes_confirmacoes)
    trilha, pendentes, linhas_csv = [], [], []
    contagens = Counter()
    for identificador in questoes:
        proposta = politicas[identificador]
        final = {**proposta, "extras_ids": list(proposta["extras_ids"]), "sinais": list(proposta["sinais"])}
        confirmacao = confirmacoes.get(identificador)
        if confirmacao is not None:
            final.update({"estado": "decidido", "decisao": "fora", "tema_central_id": "",
                          "extras_ids": [], "confianca": 0,
                          "motivo": confirmacao["justificativa"].strip(), "sinais": ["fora_confirmado_por_revisao"]})
        if final["estado"] != "decidido":
            pendentes.append({"id": identificador, "estado": final["estado"], "motivo": final["motivo"]})
        else:
            contagens[final["decisao"]] += 1
            linhas_csv.append({"id": identificador, "decisao": final["decisao"],
                               "tema_central_id": final["tema_central_id"], "extras_ids": ";".join(final["extras_ids"]),
                               "confianca": final["confianca"], "motivo": final["motivo"]})
        trilha.append({"id": identificador, "sha256_recibo": hashes_recibos[identificador + ".json"],
                       "sugestao": registros[identificador]["sugestao"], "politica": proposta,
                       "decisao": final, "confirmacao_fora": confirmacao})
    produtos = {"trilha_decisoes.jsonl": _jsonl(trilha), "pendentes_fora.jsonl": _jsonl(pendentes)}
    if not pendentes:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=_COLUNAS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(linhas_csv)
        produtos["publicacao.csv"] = buffer.getvalue().encode("utf-8")
    resumo = {
        "schema_version": 1, "procedimento": "decisoes-v1", "total_questoes": len(questoes),
        "completo": not pendentes, "pendentes_fora": len(pendentes), "ids_pendentes": [r["id"] for r in pendentes],
        "decisoes": {nome: contagens[nome] for nome in ("publicar", "revisar", "fora")},
        "politica_versao": config["versao"], "modelo": config["modelo"], "prompt_version": config["prompt_version"],
        "confirmacoes_fora": {"total": len(confirmacoes),
                              "tipos_referencia": dict(sorted(Counter(c["tipo_referencia"] for c in confirmacoes.values()).items()))},
        "confianca": {"publicar_revisar": "Autodeclarada pelo modelo; não calibrada e não equivale a precisão medida.",
                      "fora": {"valor": 0, "natureza": "sentinela_nao_aplicavel",
                               "explicacao": "Não há tema central cuja probabilidade possa ser informada; zero não estima a correção da decisão fora."}},
        "fontes_sha256": {"manifesto_lote.json": hashes_fontes[lote / "manifesto_lote.json"],
                          "manifesto.json": hash_preparacao, "politica.json": hashes_fontes[caminho_politica],
                          "ambiguidades.json": hashes_fontes[ambiguidades],
                          "confirmacoes_fora.jsonl": hashes_confirmacoes.get(caminho_confirmacoes),
                          "recibos": hashes_recibos},
        "produtos_sha256": {nome: _hash_bytes(conteudo) for nome, conteudo in produtos.items()},
        "limites": ["As decisões aplicam a política congelada; não são resultado de auditoria de precisão.",
                    "Fora depende de revisão separada identificada na trilha; referência por IA não é revisão especialista.",
                    "Sem confirmação para todos os candidatos fora, o CSV oficial não é gerado.",
                    "Motivos de revisar e fora são preservados; publicar pode ter motivo vazio."],
    }
    produtos["manifesto_decisoes.json"] = (json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    for caminho, esperado in hashes_fontes.items():
        if _hash_bytes(_ler(caminho)) != esperado:
            raise ValueError("Uma fonte mudou durante a preparação das decisões; execute novamente.")
    if (execucao / ".execucao.lock").exists() or {p.name for p in execucao.iterdir()} != permitidos:
        raise ValueError("A pasta de recibos mudou durante a preparação das decisões.")
    if saida.exists():
        for caminho in saida.iterdir():
            if caminho.name not in _PRODUTOS or caminho.is_symlink() or not caminho.is_file():
                raise ValueError("A saída contém arquivos incompatíveis com decisões.")
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".decisoes-", dir=saida) as temporaria:
        pasta = Path(temporaria)
        for nome, conteudo in produtos.items():
            (pasta / nome).write_bytes(conteudo)
        (saida / "manifesto_decisoes.json").unlink(missing_ok=True)
        if "publicacao.csv" not in produtos:
            (saida / "publicacao.csv").unlink(missing_ok=True)
        for nome in produtos:
            os.replace(pasta / nome, saida / nome)
    return resumo
