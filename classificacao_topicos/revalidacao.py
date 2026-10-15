"""Revalidação local derivada de respostas, sem alterar recibos ou fazer chamadas.

O recibo continua descrevendo as tentativas reais e seu consumo. O arquivo
adjacente registra a primeira tentativa cronológica aceita pelos validadores
atuais. Os consumidores mantêm o recibo e esta derivação em objetos separados.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from .analise_piloto import _consumo, _tentativas
from .execucao import (
    _canonico, _gravar_atomico, _hash_bytes, _json, _ler,
    _validar_cache, _validar_evidencia,
)
from .gemini import ErroGemini, _extrair_resultado
from .piloto import validar_resposta


_PROCEDIMENTO = "revalidacao-local-v1"
_CRITERIO = "primeira_tentativa_cronologica_tecnicamente_valida"
_VALIDADOR = "evidencia-literal-ou-caixa-e-espacos-v1"
_CAMPOS = {
    "schema_version", "procedimento", "id", "timestamp_utc", "fingerprint",
    "sha256_recibo_origem", "numero_tentativa_selecionada", "sha256_tentativa_selecionada",
    "criterio_selecao", "validador_evidencia", "validacao_evidencia", "sugestao",
    "sha256_registro",
}


def caminho_revalidacao(caminho_recibo: Path) -> Path:
    caminho = Path(caminho_recibo)
    if not re.fullmatch(r"Q[0-9]{4}\.json", caminho.name):
        raise ValueError("A revalidação exige o caminho de um recibo Qxxxx.json.")
    return caminho.with_name(caminho.stem + ".revalidacao.json")


def _primeira_valida(registro: dict, temas_por_id: dict, questao: dict) -> tuple[dict, dict, str]:
    if (registro.get("status") != "erro"
            or registro.get("erro", {}).get("tipo") != "ErroValidacaoLocal"):
        raise ValueError("Somente recibos com falha de validação local podem ser revalidados.")
    tentativas = _tentativas(registro)
    # Conferir também o consumo preservado; uma derivação não corrige histórico.
    _consumo(tentativas)
    identidade = ("model", "sha256_prompt", "sha256_schema", "sha256_preparacao", "thinking_level")
    for tentativa in tentativas:
        if any(tentativa.get(campo) != registro.get(campo) for campo in identidade):
            raise ValueError("Histórico contém tentativa com identidade incompatível.")
    for tentativa in tentativas:
        if (tentativa.get("status") != "erro"
                or tentativa.get("erro", {}).get("tipo") != "ErroValidacaoLocal"):
            continue
        bruto = tentativa.get("resposta_bruta")
        if not isinstance(bruto, dict):
            continue
        try:
            sugestao = validar_resposta(_extrair_resultado(bruto), registro["id"], temas_por_id)
            modo = _validar_evidencia(sugestao, questao)
        except (ErroGemini, ValueError, TypeError, KeyError):
            continue
        return tentativa, sugestao, modo
    raise ValueError("Nenhuma tentativa passa integralmente pelos validadores atuais.")


def _origem(caminho_recibo: Path, registro: dict, entrada: dict, model: str,
            schema_hash: str, preparacao_hash: str, temas_por_id: dict, questao: dict) -> str:
    if caminho_recibo.name != entrada["id"] + ".json":
        raise ValueError("O nome do recibo diverge do ID da entrada.")
    conteudo = _ler(caminho_recibo)
    validado = _validar_cache(caminho_recibo, entrada, model, schema_hash,
                            preparacao_hash, temas_por_id, questao)
    if validado != registro or _json(conteudo) != registro:
        raise ValueError("O recibo mudou ou o objeto fornecido diverge do arquivo.")
    if registro.get("sha256_preparacao") != preparacao_hash or registro.get("thinking_level") != "MEDIUM":
        raise ValueError("Identidade de preparação ou raciocínio inválida no recibo.")
    return _hash_bytes(conteudo)


def carregar_revalidacao(caminho_recibo: Path, registro: dict, entrada: dict, model: str,
                         schema_hash: str, preparacao_hash: str, temas_por_id: dict,
                         questao: dict) -> dict | None:
    """Lê e verifica o derivado; ausente retorna None, inválido interrompe.

    Repete a seleção cronológica e a validação do JSON bruto. Não aceita troca
    de tema, evidência, tentativa ou recibo, ainda que o checksum seja refeito.
    Um lock pode existir durante a leitura pelo executor que o possui.
    """
    caminho_recibo = Path(caminho_recibo)
    caminho = caminho_revalidacao(caminho_recibo)
    if not caminho.exists() and not caminho.is_symlink():
        return None
    hash_origem = _origem(caminho_recibo, registro, entrada, model, schema_hash,
                         preparacao_hash, temas_por_id, questao)
    derivado = _json(_ler(caminho))
    if not isinstance(derivado, dict) or set(derivado) != _CAMPOS:
        raise ValueError("Arquivo de revalidação contém campos ausentes ou inesperados.")
    sem_hash = {k: v for k, v in derivado.items() if k != "sha256_registro"}
    if derivado["sha256_registro"] != _hash_bytes(_canonico(sem_hash)):
        raise ValueError("Checksum da revalidação diverge do conteúdo.")
    if (type(derivado["schema_version"]) is not int or derivado["schema_version"] != 1
            or derivado["procedimento"] != _PROCEDIMENTO
            or derivado["criterio_selecao"] != _CRITERIO
            or derivado["validador_evidencia"] != _VALIDADOR):
        raise ValueError("Versão ou critério de revalidação não suportado.")
    try:
        data = datetime.fromisoformat(derivado["timestamp_utc"])
        if data.utcoffset() != timezone.utc.utcoffset(data):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("A revalidação exige timestamp UTC válido.") from None
    if (derivado["id"] != registro["id"] or derivado["fingerprint"] != registro["fingerprint"]
            or derivado["sha256_recibo_origem"] != hash_origem):
        raise ValueError("A revalidação pertence a outro recibo ou experimento.")
    tentativa, sugestao, modo = _primeira_valida(registro, temas_por_id, questao)
    if (type(derivado["numero_tentativa_selecionada"]) is not int
            or derivado["numero_tentativa_selecionada"] != tentativa["numero_tentativa"]
            or derivado["sha256_tentativa_selecionada"] != tentativa["sha256_registro"]
            or derivado["sugestao"] != sugestao or derivado["validacao_evidencia"] != modo):
        raise ValueError("A revalidação diverge da primeira tentativa tecnicamente válida.")
    if _hash_bytes(_ler(caminho_recibo)) != hash_origem:
        raise ValueError("O recibo mudou durante a leitura da revalidação.")
    return derivado


def revalidar_recibo(caminho_recibo: Path, registro: dict, entrada: dict, model: str,
                     schema_hash: str, preparacao_hash: str, temas_por_id: dict,
                     questao: dict) -> dict:
    """Grava um derivado adjacente, sem modificar o recibo nem contabilizar chamada.

    É idempotente para um derivado existente válido. Um derivado divergente
    interrompe; nunca é sobrescrito para contornar a divergência.
    """
    caminho_recibo = Path(caminho_recibo).absolute()
    caminho = caminho_revalidacao(caminho_recibo)
    for parte in (caminho_recibo, *caminho_recibo.parents):
        if parte.is_symlink() or (hasattr(parte, "is_junction") and parte.is_junction()):
            raise ValueError("A revalidação não aceita links ou junções na origem.")
    lock = caminho_recibo.parent / ".execucao.lock"
    try:
        arquivo_lock = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Existe uma execução ativa; aguarde antes de revalidar.") from None
    try:
        with arquivo_lock:
            arquivo_lock.write(datetime.now(timezone.utc).isoformat())
        existente = carregar_revalidacao(caminho_recibo, registro, entrada, model,
                                         schema_hash, preparacao_hash, temas_por_id, questao)
        if existente is not None:
            return existente
        hash_origem = _origem(caminho_recibo, registro, entrada, model, schema_hash,
                             preparacao_hash, temas_por_id, questao)
        tentativa, sugestao, modo = _primeira_valida(registro, temas_por_id, questao)
        derivado = {
            "schema_version": 1, "procedimento": _PROCEDIMENTO, "id": registro["id"],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "fingerprint": registro["fingerprint"], "sha256_recibo_origem": hash_origem,
            "numero_tentativa_selecionada": tentativa["numero_tentativa"],
            "sha256_tentativa_selecionada": tentativa["sha256_registro"],
            "criterio_selecao": _CRITERIO, "validador_evidencia": _VALIDADOR,
            "validacao_evidencia": modo, "sugestao": sugestao,
        }
        if _hash_bytes(_ler(caminho_recibo)) != hash_origem:
            raise ValueError("O recibo mudou durante a revalidação; nenhum derivado foi gravado.")
        if caminho.exists() or caminho.is_symlink():
            raise ValueError("Outro derivado surgiu durante a revalidação; confira os arquivos.")
        _gravar_atomico(caminho, derivado)
        return derivado
    finally:
        lock.unlink(missing_ok=True)


def status_efetivo(registro: dict, revalidacao: dict | None = None) -> str:
    """Estado técnico para uso após carregar_revalidacao; não modifica a origem."""
    return "sucesso" if revalidacao is not None else registro["status"]


def sugestao_efetiva(registro: dict, revalidacao: dict | None = None) -> dict | None:
    """Sugestão técnica aceita; a política temática continua sendo etapa separada."""
    if revalidacao is not None:
        return revalidacao["sugestao"]
    return registro.get("sugestao") if registro["status"] == "sucesso" else None
