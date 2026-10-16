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
    _validar_evidencia,
)
from .piloto import esquema_resposta, validar_resposta
from .politica import aplicar_politica
from .revalidacao import carregar_revalidacao, status_efetivo, sugestao_efetiva


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


def _carregar_confirmacoes(caminho: Path | None, candidatos: set[str],
                          temas: dict, questoes: dict) -> tuple[dict, dict]:
    if caminho is None:
        return {}, {}
    conteudo = _ler(caminho)
    confirmacoes = {}
    campos = {"id", "sem_tema", "situacao", "justificativa", "responsavel", "tipo_referencia"}
    for linha in conteudo.decode("utf-8-sig").split("\n"):
        if not linha.strip():
            continue
        item = _json(linha)
        if not isinstance(item, dict) or type(item.get("sem_tema")) is not bool:
            raise ValueError("Revisão fora exige sem_tema booleano.")
        esperados = campos if item["sem_tema"] else campos | {"sugestao_corrigida"}
        if set(item) != esperados:
            raise ValueError("Confirmação fora contém campos ausentes ou inesperados.")
        identificador = item["id"]
        if not isinstance(identificador, str) or identificador not in candidatos:
            raise ValueError("Confirmação fora só pode referir um candidato sem tema deste lote.")
        if identificador in confirmacoes:
            raise ValueError("Confirmação fora duplicada.")
        situacao = "confirmado" if item["sem_tema"] else "tema_encontrado"
        if item["situacao"] != situacao:
            raise ValueError("Situação da revisão fora é incompatível com sem_tema.")
        if not isinstance(item["tipo_referencia"], str) or item["tipo_referencia"] not in {"IA", "especialista"}:
            raise ValueError("Tipo de referência da confirmação deve ser IA ou especialista.")
        for campo in ("justificativa", "responsavel"):
            if not isinstance(item[campo], str) or not item[campo].strip():
                raise ValueError("Confirmação fora exige justificativa e responsável textuais não vazios.")
        if not item["sem_tema"]:
            corrigida = validar_resposta(item["sugestao_corrigida"], identificador, temas)
            if corrigida["sem_tema"] or corrigida["requer_revisao"] is not True:
                raise ValueError("Tema encontrado exige sugestão com sem_tema false e requer_revisao true.")
            nivel = temas[corrigida["tema_central_id"]].get("nivel")
            if isinstance(nivel, str) and nivel.isascii() and nivel.isdecimal():
                nivel = int(nivel)
            if type(nivel) is not int or nivel <= 0:
                raise ValueError("A sugestão corrigida exige tema central ativo de nível maior que zero.")
            _validar_evidencia(corrigida, questoes[identificador])
            item = {**item, "sugestao_corrigida": corrigida}
        confirmacoes[identificador] = item
    return confirmacoes, {caminho: _hash_bytes(conteudo)}


def _jsonl(linhas: list[dict]) -> bytes:
    return b"".join(_canonico(linha) + b"\n" for linha in linhas)


def _saida_existente(saida: Path, ids: list[str], temas: dict) -> dict[str, bytes] | None:
    """Confere a saída antes de qualquer substituição, inclusive a preliminar."""
    if not saida.exists():
        return None
    arquivos = list(saida.iterdir())
    if not arquivos:
        return None
    if any(p.name not in _PRODUTOS or p.is_symlink() or not p.is_file() for p in arquivos):
        raise ValueError("A saída contém arquivos incompatíveis com decisões; use uma nova pasta.")
    existentes = {p.name: _ler(p) for p in arquivos}
    try:
        manifesto = _json(existentes["manifesto_decisoes.json"])
        if (not isinstance(manifesto, dict) or type(manifesto.get("schema_version")) is not int
                or manifesto["schema_version"] != 1 or manifesto.get("procedimento") != "decisoes-v1"
                or type(manifesto.get("completo")) is not bool):
            raise ValueError("Versão ou estado do manifesto inválido.")
        completo = manifesto["completo"]
        total, pendentes = manifesto.get("total_questoes"), manifesto.get("pendentes_fora")
        contagens = manifesto.get("decisoes")
        if (type(total) is not int or total != len(ids) or type(pendentes) is not int
                or not 0 <= pendentes <= total or completo != (pendentes == 0)
                or not isinstance(contagens, dict) or set(contagens) != {"publicar", "revisar", "fora"}
                or any(type(n) is not int or n < 0 for n in contagens.values())
                or sum(contagens.values()) + pendentes != total):
            raise ValueError("Contagens ou conclusão do manifesto inválidas.")
        nomes = {"trilha_decisoes.jsonl", "pendentes_fora.jsonl"}
        if completo:
            nomes.add("publicacao.csv")
        declarados = manifesto.get("produtos_sha256")
        # Um CSV presente nunca pode ser tratado como saída preliminar apenas
        # porque alguém retirou ou alterou a indicação de conclusão do manifesto.
        if (not isinstance(declarados, dict) or set(declarados) != nomes
                or set(existentes) != nomes | {"manifesto_decisoes.json"}):
            raise ValueError("Arquivos existentes divergem dos produtos declarados.")
        for nome, esperado in declarados.items():
            if (not isinstance(esperado, str) or not re.fullmatch(r"[a-f0-9]{64}", esperado)
                    or _hash_bytes(existentes[nome]) != esperado):
                raise ValueError("Hash divergente em produto de decisões.")
        lista_pendentes = [_json(linha) for linha in existentes["pendentes_fora.jsonl"].decode("utf-8-sig").split("\n")
                          if linha.strip()]
        ids_pendentes = [item["id"] for item in lista_pendentes]
        if (len(ids_pendentes) != pendentes or ids_pendentes != manifesto.get("ids_pendentes")
                or len(set(ids_pendentes)) != len(ids_pendentes) or not set(ids_pendentes).issubset(ids)):
            raise ValueError("Pendências existentes divergem do manifesto.")
        if completo:
            # Reutiliza somente a validação estrutural, sem sortear auditoria.
            from .auditoria import _csv_decisoes, _validar_manifesto_decisoes
            fontes = manifesto["fontes_sha256"]
            for nome in ("manifesto.json", "manifesto_lote.json", "politica.json"):
                if not isinstance(fontes[nome], str) or not re.fullmatch(r"[a-f0-9]{64}", fontes[nome]):
                    raise ValueError("Hash de fonte inválido no manifesto.")
            decisoes = _csv_decisoes(existentes["publicacao.csv"], ids, temas)
            _validar_manifesto_decisoes(manifesto, decisoes, declarados["publicacao.csv"],
                                       fontes["manifesto.json"], fontes["manifesto_lote.json"], fontes["politica.json"])
    except (ValueError, KeyError, TypeError) as erro:
        raise ValueError("A saída existente tem manifesto ou produtos inválidos; preserve-a e use uma nova pasta.") from erro
    return existentes


def preparar_decisoes(lote: Path, preparacao: Path, execucao: Path, politica: Path,
                      saida: Path, *, confirmacoes_fora: Path | None = None) -> dict:
    """Gera trilha completa; publica CSV somente com todas as decisões resolvidas.

    Exige sucesso técnico em todos os IDs preparados e revisão explícita para
    cada sem_tema. Tema encontrado pela revisão sempre segue para revisar.
    Não acessa credenciais, redes ou modelos.
    Uma saída completa só é reutilizada quando permanece byte a byte idêntica;
    mudanças exigem nova pasta. Saídas preliminares podem avançar para completas.
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
    anteriores = _saida_existente(saida, list(questoes), temas)
    recibos_esperados = {e["id"] + ".json" for e in entradas}
    sidecars_permitidos = {e["id"] + ".revalidacao.json" for e in entradas}
    arquivos_iniciais = {p.name for p in execucao.iterdir()}
    if (not recibos_esperados.issubset(arquivos_iniciais)
            or not arquivos_iniciais.issubset(recibos_esperados | sidecars_permitidos)):
        raise ValueError("É necessário um recibo para cada questão, sem arquivos extras ou IDs ausentes.")
    schema_hash = _hash_bytes(_canonico(esquema_resposta()))
    entradas_por_id = {e["id"]: e for e in entradas}
    registros, revalidacoes, politicas, hashes_recibos, hashes_revalidacoes = {}, {}, {}, {}, {}
    # A preparação preserva a ordem original, independentemente da ordem do lote.
    for identificador, questao in questoes.items():
        arquivo = execucao / (identificador + ".json")
        hash_recibo = _hash_bytes(_ler(arquivo))
        registro = _validar_cache(arquivo, entradas_por_id[identificador], config["modelo"],
                                  schema_hash, hash_preparacao, temas, questao)
        # O histórico é sempre o original: o sidecar não é uma chamada adicional
        # e não substitui recibos ou suas contagens de consumo.
        _tentativas(registro)
        caminho_revalidacao = execucao / (identificador + ".revalidacao.json")
        if caminho_revalidacao.name in arquivos_iniciais:
            hash_revalidacao = _hash_bytes(_ler(caminho_revalidacao))
            hashes_fontes[caminho_revalidacao] = hash_revalidacao
            hashes_revalidacoes[caminho_revalidacao.name] = hash_revalidacao
        revalidacao = carregar_revalidacao(
            arquivo, registro, entradas_por_id[identificador], config["modelo"],
            schema_hash, hash_preparacao, temas, questao)
        if status_efetivo(registro, revalidacao) != "sucesso":
            raise ValueError("Todos os recibos devem ter sucesso técnico antes de preparar decisões.")
        registros[identificador] = registro
        revalidacoes[identificador] = revalidacao
        hashes_recibos[arquivo.name] = hash_recibo
        hashes_fontes[arquivo] = hash_recibo
        politicas[identificador] = aplicar_politica(
            sugestao_efetiva(registro, revalidacao), temas, set(config["ids_ambiguos"]),
            confianca_minima=config["confianca_minima"], max_extras_publicar=config["max_extras_publicar"])
    candidatos = {i for i, r in politicas.items() if r["estado"] == "pendente_confirmacao_fora"}
    confirmacoes, hashes_confirmacoes = _carregar_confirmacoes(caminho_confirmacoes, candidatos, temas, questoes)
    hashes_fontes.update(hashes_confirmacoes)
    trilha, pendentes, linhas_csv = [], [], []
    confirmadas_sem_tema, temas_encontrados = [], []
    contagens = Counter()
    for identificador in questoes:
        proposta = politicas[identificador]
        final = {**proposta, "extras_ids": list(proposta["extras_ids"]), "sinais": list(proposta["sinais"])}
        confirmacao = confirmacoes.get(identificador)
        corrigida, politica_apos_revisao = None, None
        origem_confianca = "sugestao_original_do_modelo"
        if confirmacao is not None:
            if confirmacao["sem_tema"]:
                confirmadas_sem_tema.append(identificador)
                origem_confianca = "sentinela_nao_aplicavel"
                final.update({"estado": "decidido", "decisao": "fora", "tema_central_id": "",
                              "extras_ids": [], "confianca": 0,
                              "motivo": confirmacao["justificativa"].strip(), "sinais": ["fora_confirmado_por_revisao"]})
            else:
                temas_encontrados.append(identificador)
                corrigida = confirmacao["sugestao_corrigida"]
                origem_confianca = "sugestao_corrigida_da_revisao"
                politica_apos_revisao = aplicar_politica(
                    corrigida, temas, set(config["ids_ambiguos"]),
                    confianca_minima=config["confianca_minima"], max_extras_publicar=config["max_extras_publicar"])
                if politica_apos_revisao["estado"] != "decidido" or politica_apos_revisao["decisao"] != "revisar":
                    raise ValueError("Tema encontrado por revisão deve resultar exclusivamente em revisar.")
                motivo = "Revisão encontrou tema: " + " ".join(confirmacao["justificativa"].split())
                if len(motivo) > 280:
                    motivo = motivo[:277].rstrip() + "..."
                final = {**politica_apos_revisao, "extras_ids": list(politica_apos_revisao["extras_ids"]),
                         "motivo": motivo,
                         "sinais": ["fora_rejeitado_por_revisao", *politica_apos_revisao["sinais"]]}
        if final["estado"] != "decidido":
            pendentes.append({"id": identificador, "estado": final["estado"], "motivo": final["motivo"]})
        else:
            contagens[final["decisao"]] += 1
            linhas_csv.append({"id": identificador, "decisao": final["decisao"],
                               "tema_central_id": final["tema_central_id"], "extras_ids": ";".join(final["extras_ids"]),
                               "confianca": final["confianca"], "motivo": final["motivo"]})
        registro, revalidacao = registros[identificador], revalidacoes[identificador]
        trilha.append({"id": identificador, "sha256_recibo": hashes_recibos[identificador + ".json"],
                       "sha256_revalidacao": hashes_revalidacoes.get(identificador + ".revalidacao.json"),
                       "revalidacao": revalidacao, "status_recibo": registro["status"],
                       "status_efetivo": status_efetivo(registro, revalidacao),
                       "sugestao": sugestao_efetiva(registro, revalidacao), "politica": proposta,
                       "decisao": final, "confirmacao_fora": confirmacao,
                       "sugestao_corrigida": corrigida, "politica_apos_revisao": politica_apos_revisao,
                       "origem_confianca": origem_confianca})
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
        "revisoes_fora": {"confirmadas_sem_tema": len(confirmadas_sem_tema),
                          "ids_confirmadas_sem_tema": confirmadas_sem_tema,
                          "temas_encontrados": len(temas_encontrados), "ids_temas_encontrados": temas_encontrados},
        "confianca": {"publicar_revisar": "Sem correção de fora, autodeclarada pelo modelo original; não calibrada e não equivale a precisão medida.",
                      "revisar_apos_rejeicao_fora": "Autodeclarada pelo revisor na sugestao_corrigida; não calibrada. A confiança original permanece separada na sugestao da trilha.",
                      "fora": {"valor": 0, "natureza": "sentinela_nao_aplicavel",
                               "explicacao": "Não há tema central cuja probabilidade possa ser informada; zero não estima a correção da decisão fora."}},
        "fontes_sha256": {"manifesto_lote.json": hashes_fontes[lote / "manifesto_lote.json"],
                          "manifesto.json": hash_preparacao, "politica.json": hashes_fontes[caminho_politica],
                          "ambiguidades.json": hashes_fontes[ambiguidades],
                          "confirmacoes_fora.jsonl": hashes_confirmacoes.get(caminho_confirmacoes),
                          "recibos": hashes_recibos, "revalidacoes": hashes_revalidacoes},
        "produtos_sha256": {nome: _hash_bytes(conteudo) for nome, conteudo in produtos.items()},
        "limites": ["As decisões aplicam a política congelada; não são resultado de auditoria de precisão.",
                    "Fora depende de revisão separada identificada na trilha; referência por IA não é revisão especialista.",
                    "Sem revisão conclusiva para todos os candidatos fora, o CSV oficial não é gerado.",
                    "Tema encontrado na revisão de fora sempre resulta em revisar, nunca publicar.",
                    "Justificativas completas são preservadas na trilha; o motivo de tema encontrado no CSV usa até 280 caracteres. Publicar pode ter motivo vazio."],
    }
    produtos["manifesto_decisoes.json"] = (json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    for caminho, esperado in hashes_fontes.items():
        if _hash_bytes(_ler(caminho)) != esperado:
            raise ValueError("Uma fonte mudou durante a preparação das decisões; execute novamente.")
    if (execucao / ".execucao.lock").exists() or {p.name for p in execucao.iterdir()} != arquivos_iniciais:
        raise ValueError("A pasta de recibos mudou durante a preparação das decisões.")
    if _saida_existente(saida, list(questoes), temas) != anteriores:
        raise ValueError("A saída de decisões mudou durante o processamento; preserve-a e use uma nova pasta.")
    if anteriores == produtos:
        return resumo
    if anteriores is not None and "publicacao.csv" in anteriores:
        raise ValueError("A saída completa está congelada e diverge das novas decisões; use uma nova pasta.")
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
