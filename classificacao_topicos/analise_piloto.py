"""Comparação offline entre sugestões do piloto e revisões provisórias de IA.

Concordância entre essas propostas não mede precisão e não autoriza publicação.
Este módulo não carrega credenciais nem chama modelos.
"""

from __future__ import annotations

from collections import Counter
import csv
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile

from .execucao import (
    _CAMPOS_TOKENS, _canonico, _hash_bytes, _json, _ler,
    _validar_cache, _validar_entradas, _validar_saida,
)
from .piloto import esquema_resposta


_COMPARACOES = ("exata", "diferenca_mesmo_ramo", "divergencia", "inconclusivo", "sem_resposta")
_PRODUTOS = {"comparacao_piloto.csv", "resumo_piloto.json"}


def _carregar_revisoes(pasta: Path, ids: set[str], temas: dict) -> tuple[dict, dict]:
    if not pasta.is_dir():
        raise ValueError("A pasta das revisões não existe.")
    revisoes, hashes = {}, {}
    for caminho in sorted(pasta.glob("proposta_*.jsonl")):
        conteudo = _ler(caminho)
        hashes[caminho] = _hash_bytes(conteudo)
        for linha in conteudo.decode("utf-8-sig").split("\n"):
            if not linha.strip():
                continue
            revisao = _json(linha)
            if not isinstance(revisao, dict):
                raise ValueError("Revisão deve ser um objeto JSON.")
            identificador = revisao.get("id")
            if not isinstance(identificador, str) or identificador not in ids:
                raise ValueError("Revisão contém ID ausente do piloto.")
            if identificador in revisoes:
                raise ValueError("Há revisões duplicadas para uma questão do piloto.")
            central = revisao.get("tema_central_id")
            if not isinstance(central, str):
                raise ValueError("Tema central da revisão deve ser texto, inclusive quando vazio.")
            if revisao.get("situacao") not in {"provisorio", "inconclusivo"}:
                raise ValueError("Situação de revisão não reconhecida.")
            sem_tema = revisao.get("sem_tema")
            if sem_tema is not None and type(sem_tema) is not bool:
                raise ValueError("sem_tema da revisão deve ser booleano ou null.")
            for campo in ("justificativa", "referencia_tipo"):
                if not isinstance(revisao.get(campo), str) or not revisao[campo].strip():
                    raise ValueError("Revisão sem justificativa ou tipo de referência textual.")
            limitacoes = revisao.get("limitacoes")
            if not isinstance(limitacoes, list) or any(not isinstance(v, str) for v in limitacoes):
                raise ValueError("Limitações da revisão devem formar uma lista textual.")
            relacionados = [central] if central else []
            for campo in ("extras_ids", "temas_alternativos"):
                valores = revisao.get(campo)
                if not isinstance(valores, list) or any(not isinstance(v, str) or not v for v in valores):
                    raise ValueError("Listas de IDs inválidas na revisão.")
                if len(valores) != len(set(valores)):
                    raise ValueError("Lista da revisão contém IDs duplicados.")
                relacionados.extend(valores)
            if any(i not in temas or temas[i].get("status") != "active" for i in relacionados):
                raise ValueError("Revisão contém tema inexistente ou inativo.")
            if sem_tema is True and (central or revisao["extras_ids"]):
                raise ValueError("Revisão sem tema não pode afirmar tema central ou extras.")
            if revisao["situacao"] == "provisorio" and sem_tema is False and not central:
                raise ValueError("Revisão provisória com tema exige um ID central.")
            revisoes[identificador] = revisao
    return revisoes, hashes


def _ancestrais(identificador: str, temas: dict) -> set[str]:
    resultado = set()
    atual = identificador
    while atual:
        if atual not in temas or atual in resultado:
            raise ValueError("A hierarquia de temas contém pai ausente ou ciclo.")
        resultado.add(atual)
        atual = temas[atual].get("parent_id", "")
    resultado.discard(identificador)
    return resultado


def _comparar(sugestao: dict | None, revisao: dict | None, temas: dict) -> tuple[str, str]:
    if sugestao is None:
        return "sem_resposta", "Não há sugestão tecnicamente válida neste recibo."
    if revisao is None:
        return "inconclusivo", "Não foi localizada revisão prévia para a questão."
    if revisao["situacao"] == "inconclusivo" or revisao["sem_tema"] is None:
        return "inconclusivo", "A própria revisão prévia permanece inconclusiva."
    if sugestao["sem_tema"] != revisao["sem_tema"]:
        return "divergencia", "As propostas discordam sobre haver tema adequado na árvore."
    if sugestao["sem_tema"]:
        return "exata", "Ambas propõem ausência de tema; isso não confirma a decisão final fora."
    modelo_id, revisao_id = sugestao["tema_central_id"], revisao["tema_central_id"]
    if modelo_id == revisao_id:
        return "exata", "Mesmo ID central; extras e candidatos não integram este indicador."
    if modelo_id in _ancestrais(revisao_id, temas) or revisao_id in _ancestrais(modelo_id, temas):
        return "diferenca_mesmo_ramo", "Relação ancestral/descendente; indicador descritivo, sem aplicar equivalência oficial."
    return "divergencia", "IDs centrais distintos, sem relação ancestral/descendente; irmãos permanecem distintos."


def _tentativas(registro: dict) -> list[dict]:
    anteriores = registro.get("tentativas_anteriores", [])
    if not isinstance(anteriores, list) or registro.get("numero_tentativa") != len(anteriores) + 1:
        raise ValueError("Histórico de tentativas inválido no recibo.")
    tentativas = [*anteriores, registro]
    for numero, tentativa in enumerate(tentativas, 1):
        if not isinstance(tentativa, dict) or tentativa.get("numero_tentativa") != numero:
            raise ValueError("Tentativas fora de ordem ou duplicadas no recibo.")
        if numero < len(tentativas) and "tentativas_anteriores" in tentativa:
            raise ValueError("Histórico aninhado duplicaria tentativas; confira o recibo.")
        if tentativa.get("id") != registro["id"] or tentativa.get("fingerprint") != registro["fingerprint"]:
            raise ValueError("Histórico pertence a outro experimento.")
        sem_hash = {k: v for k, v in tentativa.items() if k != "sha256_registro"}
        if tentativa.get("sha256_registro") != _hash_bytes(_canonico(sem_hash)):
            raise ValueError("Checksum de tentativa divergente.")
        if tentativa.get("status") not in {"sucesso", "erro"}:
            raise ValueError("Tentativa com status inválido.")
    return tentativas


def _consumo(tentativas: list[dict]) -> dict:
    somas, informados, ausentes = {}, {}, {}
    duracoes = []
    sem_uso = 0
    modelos, versoes = Counter(), Counter()
    sem_versao = 0
    for tentativa in tentativas:
        modelos[tentativa["model"]] += 1
        bruto = tentativa.get("resposta_bruta", {})
        versao = bruto.get("modelVersion") if isinstance(bruto, dict) else None
        if isinstance(versao, str) and versao:
            versoes[versao] += 1
        else:
            sem_versao += 1
        usage = tentativa.get("usage_metadata")
        if isinstance(bruto, dict) and "usageMetadata" in bruto and bruto["usageMetadata"] != usage:
            raise ValueError("Consumo resumido diverge do recibo bruto.")
        if not isinstance(usage, dict):
            sem_uso += 1
            usage = {}
        for campo in _CAMPOS_TOKENS:
            if campo not in usage:
                ausentes[campo] = ausentes.get(campo, 0) + 1
                continue
            valor = usage[campo]
            if type(valor) is not int or valor < 0:
                raise ValueError("Contagem de tokens inválida em recibo.")
            somas[campo] = somas.get(campo, 0) + valor
            informados[campo] = informados.get(campo, 0) + 1
        duracao = tentativa.get("duracao_segundos")
        if duracao is not None:
            if type(duracao) not in {int, float} or not math.isfinite(duracao) or duracao < 0:
                raise ValueError("Duração inválida em recibo.")
            duracoes.append(duracao)
    return {
        "tentativas": len(tentativas), "tokens_observados": somas,
        "tentativas_com_campo": informados, "tentativas_sem_campo": ausentes,
        "tentativas_sem_usage_metadata": sem_uso,
        "duracao_chamadas_segundos_observada": sum(duracoes) if duracoes else None,
        "tentativas_com_duracao": len(duracoes), "tentativas_sem_duracao": len(tentativas) - len(duracoes),
        "modelos_solicitados": dict(sorted(modelos.items())),
        "versoes_retornadas": dict(sorted(versoes.items())), "tentativas_sem_versao": sem_versao,
    }


def _caminho(identificador: str, temas: dict) -> str:
    if not identificador:
        return ""
    tema = temas[identificador]
    return tema.get("caminho_calculado", tema.get("caminho", tema.get("titulo", identificador)))


def _lista(valores: list) -> str:
    return " | ".join(str(v) for v in valores)


def _linha(identificador: str, registro: dict | None, revisao: dict | None, temas: dict) -> dict:
    sugestao = registro.get("sugestao") if registro and registro["status"] == "sucesso" else None
    comparacao, observacao = _comparar(sugestao, revisao, temas)
    tentativa = _tentativas(registro) if registro else []
    consumo = _consumo(tentativa)
    bruto = registro.get("resposta_bruta", {}) if registro else {}
    erro = registro.get("erro", {}) if registro else {}
    linha = {
        "id": identificador, "status_tecnico": registro["status"] if registro else "sem_recibo",
        "comparacao_central": comparacao, "observacao_comparacao": observacao,
        "modelo": registro["model"] if registro else "",
        "versao_retornada": bruto.get("modelVersion", "") if isinstance(bruto, dict) else "",
        "tentativas": consumo["tentativas"],
        "duracao_chamadas_segundos_observada": consumo["duracao_chamadas_segundos_observada"],
        "total_tokens_observados": consumo["tokens_observados"].get("totalTokenCount"),
        "tentativas_sem_total_tokens": consumo["tentativas_sem_campo"].get("totalTokenCount", 0),
        "erro_tipo": erro.get("tipo", ""), "erro_mensagem": erro.get("mensagem", ""),
    }
    for prefixo, proposta in (("modelo", sugestao), ("revisao", revisao)):
        central = proposta["tema_central_id"] if proposta else ""
        linha[prefixo + "_tema_central_id"] = central
        linha[prefixo + "_caminho_central"] = _caminho(central, temas)
        linha[prefixo + "_sem_tema"] = proposta["sem_tema"] if proposta else None
        for campo in ("extras_ids", "temas_alternativos"):
            valores = proposta[campo] if proposta else []
            linha[prefixo + "_" + campo] = _lista(valores)
            linha[prefixo + "_" + campo + "_caminhos"] = _lista([_caminho(i, temas) for i in valores])
    linha.update({
        "modelo_requer_revisao": sugestao["requer_revisao"] if sugestao else None,
        "modelo_confianca_autodeclarada": sugestao["confianca_autodeclarada"] if sugestao else None,
        "modelo_motivo": sugestao["motivo"] if sugestao else "",
        "modelo_evidencia": sugestao["evidencia"] if sugestao else "",
        "revisao_situacao": revisao["situacao"] if revisao else "ausente",
        "revisao_justificativa": revisao["justificativa"] if revisao else "",
        "revisao_limitacoes": _lista(revisao["limitacoes"]) if revisao else "",
        "referencia_tipo": revisao["referencia_tipo"] if revisao else "ausente",
    })
    return linha


def analisar_piloto(piloto: Path, preparacao: Path, execucao: Path,
                    revisoes: Path, saida: Path) -> dict:
    """Gera CSV comparativo e resumo de rastreabilidade, sem estimar precisão."""
    piloto, preparacao = Path(piloto).resolve(), Path(preparacao).resolve()
    execucao, revisoes = Path(execucao).resolve(), Path(revisoes).resolve()
    entradas, temas, questoes, hash_preparacao, raiz = _validar_entradas(piloto, preparacao)
    saida = _validar_saida(Path(saida), piloto=piloto, preparacao=preparacao, raiz=raiz)
    for entrada in (execucao, revisoes):
        if saida == entrada or saida in entrada.parents or entrada in saida.parents:
            raise ValueError("A análise deve ter saída separada da execução e das revisões.")
    if not execucao.is_dir():
        raise ValueError("A pasta de execução não existe.")
    if (execucao / ".execucao.lock").exists():
        raise ValueError("A execução ainda está ativa; aguarde antes de analisar os recibos.")
    ids = {e["id"] for e in entradas}
    revisoes_por_id, hashes_revisoes = _carregar_revisoes(revisoes, ids, temas)
    registros, hashes_recibos = {}, {}
    schema_hash = _hash_bytes(_canonico(esquema_resposta()))
    entradas_por_id = {e["id"]: e for e in entradas}
    for caminho in sorted(execucao.iterdir()):
        if not re.fullmatch(r"Q[0-9]{4}\.json", caminho.name) or caminho.stem not in ids:
            raise ValueError("A execução contém arquivos incompatíveis com o piloto.")
        conteudo = _ler(caminho)
        registro = _json(conteudo)
        modelo = registro.get("model") if isinstance(registro, dict) else None
        if not isinstance(modelo, str) or not re.fullmatch(r"gemini-[a-z0-9]+(?:[.-][a-z0-9]+)*", modelo):
            raise ValueError("Recibo com identificador de modelo inválido.")
        registros[caminho.stem] = _validar_cache(
            caminho, entradas_por_id[caminho.stem], modelo, schema_hash, hash_preparacao,
            temas, questoes[caminho.stem])
        hashes_recibos[caminho] = _hash_bytes(conteudo)
    linhas = [_linha(e["id"], registros.get(e["id"]), revisoes_por_id.get(e["id"]), temas) for e in entradas]
    todas_tentativas = [t for registro in registros.values() for t in _tentativas(registro)]
    contagens = Counter(linha["comparacao_central"] for linha in linhas)
    sugestoes = [r["sugestao"] for r in registros.values() if r["status"] == "sucesso"]
    resumo = {
        "schema_version": 1, "procedimento": "analise-piloto-v1", "total_questoes": len(entradas),
        "status_tecnico": dict(sorted(Counter(linha["status_tecnico"] for linha in linhas).items())),
        "comparacao_central": {nome: contagens[nome] for nome in _COMPARACOES},
        "ids_por_comparacao": {nome: [linha["id"] for linha in linhas if linha["comparacao_central"] == nome] for nome in _COMPARACOES},
        "revisoes": {"presentes": len(revisoes_por_id), "ausentes": len(ids - revisoes_por_id.keys()),
                     "situacoes": dict(sorted(Counter(r["situacao"] for r in revisoes_por_id.values()).items())),
                     "referencia_tipos": dict(sorted(Counter(r["referencia_tipo"] for r in revisoes_por_id.values()).items()))},
        "flags_sugestoes_validas": {"total": len(sugestoes),
                                   "requer_revisao": sum(s["requer_revisao"] for s in sugestoes),
                                   "sem_tema": sum(s["sem_tema"] for s in sugestoes)},
        "consumo": _consumo(todas_tentativas),
        "fontes_sha256": {"manifesto_preparacao": hash_preparacao,
                          "manifesto_piloto": _hash_bytes(_ler(piloto / "manifesto_piloto.json")),
                          "recibos": {p.name: h for p, h in hashes_recibos.items()},
                          "revisoes": {p.name: h for p, h in hashes_revisoes.items()}},
        "limites": [
            "Comparação entre sugestões de modelo e revisão provisória por IA; não há gabarito especialista.",
            "O piloto é uma seleção de desenvolvimento; os indicadores não estimam precisão nem comprovam a meta de 95%.",
            "Exata compara tema central ou ausência de tema; extras e candidatos ficam expostos no CSV.",
            "Diferença no mesmo ramo indica ancestralidade direta ou indireta; não aplica interpretação ampliada da regra oficial.",
            "Revisão inconclusiva permanece inconclusiva mesmo quando os IDs coincidem.",
            "Não são atribuídas decisões finais publicar, revisar ou fora.",
            "Consumo inclui todas as tentativas deste diretório, sem duplicar histórico; verificações sintéticas e outros diretórios ficam fora.",
            "Campos de consumo ausentes não são estimados como zero; duração soma chamadas e não inclui espera entre requisições.",
        ],
    }
    arquivo_csv = io.StringIO(newline="")
    writer = csv.DictWriter(arquivo_csv, fieldnames=list(linhas[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(linhas)
    csv_bytes = arquivo_csv.getvalue().encode("utf-8-sig")
    resumo["produtos_sha256"] = {"comparacao_piloto.csv": _hash_bytes(csv_bytes)}
    produtos = {"comparacao_piloto.csv": csv_bytes,
                "resumo_piloto.json": (json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")}
    # Recibos e revisões precisam permanecer idênticos ao snapshot analisado.
    for caminho, esperado in {**hashes_recibos, **hashes_revisoes}.items():
        if _hash_bytes(_ler(caminho)) != esperado:
            raise ValueError("Uma fonte mudou durante a análise; execute novamente.")
    if (execucao / ".execucao.lock").exists():
        raise ValueError("Uma execução iniciou durante a análise; tente após sua conclusão.")
    if saida.exists():
        for caminho in saida.iterdir():
            if caminho.name not in _PRODUTOS or caminho.is_symlink() or not caminho.is_file():
                raise ValueError("A saída da análise contém arquivos incompatíveis.")
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".analise-", dir=saida) as temporaria:
        pasta = Path(temporaria)
        for nome, conteudo in produtos.items():
            (pasta / nome).write_bytes(conteudo)
        (saida / "resumo_piloto.json").unlink(missing_ok=True)
        for nome in produtos:
            os.replace(pasta / nome, saida / nome)
    return resumo
