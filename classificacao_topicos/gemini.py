"""Cliente REST mínimo da Gemini Developer API, sem dependências externas.

Contrato baseado na documentação oficial consultada em 14/10/2026. Ainda precisa
ser validado por uma chamada real: os testes locais substituem toda a rede.
Não há repetição automática, troca de modelo ou ativação de faturamento.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


MODELO_PADRAO = "gemini-3.8-flash"
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
_MODELO_RE = re.compile(r"gemini-[a-z0-9]+(?:[.-][a-z0-9]+)*")


class ErroGemini(RuntimeError):
    """Falha de configuração, transporte ou resposta, sem detalhes secretos."""

    def __init__(self, mensagem: str, *, resposta: dict | None = None,
                 duracao_segundos: float | None = None):
        super().__init__(mensagem)
        # Recibo disponível apenas em memória, separado da mensagem segura.
        self.resposta = resposta
        self.duracao_segundos = duracao_segundos


def _validar_modelo(model: str) -> str:
    if not isinstance(model, str) or len(model) > 128 or not _MODELO_RE.fullmatch(model):
        raise ErroGemini("Modelo Gemini inválido: use somente o identificador do modelo.")
    return model


def _validar_chave(api_key: str) -> str:
    if not isinstance(api_key, str) or not api_key or any(
        caractere.isspace() or ord(caractere) < 33 or ord(caractere) > 126
        for caractere in api_key
    ):
        raise ErroGemini("GEMINI_API_KEY ausente ou inválida. Configure a chave localmente.")
    return api_key


def _ler_env(caminho: Path, *, obrigatorio: bool) -> dict[str, str]:
    try:
        conteudo = caminho.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        if obrigatorio:
            raise ErroGemini("O arquivo de configuração .env informado não existe.") from None
        return {}
    except (OSError, UnicodeError):
        raise ErroGemini("Não foi possível ler o arquivo .env como texto UTF-8.") from None
    valores = {}
    for numero, linha in enumerate(conteudo.splitlines(), start=1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        nome, separador, valor = linha.partition("=")
        nome = nome.strip()
        if not separador or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nome):
            raise ErroGemini(f"Arquivo .env inválido na linha {numero}: use NOME=valor.")
        valor = valor.strip()
        if valor.startswith(("'", '"')):
            if len(valor) < 2 or valor[-1] != valor[0]:
                raise ErroGemini(f"Aspas não fechadas no arquivo .env, linha {numero}.")
            valor = valor[1:-1]
        if nome in {"GEMINI_API_KEY", "GEMINI_MODEL"}:
            valores[nome] = valor
    return valores


def carregar_configuracao(env_path: Path | None = None) -> dict:
    """Lê chave/modelo sem imprimir, persistir ou expandir valores.

    Variáveis do processo têm precedência, inclusive quando vazias. Para campos
    ausentes, lê ``env_path`` ou ``.env`` no diretório atual. O .env padrão pode
    não existir; um caminho explicitamente informado deve existir se necessário.
    Valores entre aspas simples/duplas são aceitos; comandos, escapes e variáveis
    dentro deles permanecem literais. O resultado contém a chave: não o registre.
    """
    nomes = ("GEMINI_API_KEY", "GEMINI_MODEL")
    arquivo = {}
    if any(nome not in os.environ for nome in nomes):
        arquivo = _ler_env(Path(env_path) if env_path is not None else Path(".env"),
                           obrigatorio=env_path is not None)
    chave = os.environ.get("GEMINI_API_KEY", arquivo.get("GEMINI_API_KEY", ""))
    modelo = os.environ.get("GEMINI_MODEL", arquivo.get("GEMINI_MODEL", MODELO_PADRAO))
    return {"api_key": _validar_chave(chave), "model": _validar_modelo(modelo)}


class _SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Não encaminhar a chave para outro destino em uma resposta HTTP 30x.
        return None


def urlopen(requisicao: Request, *, timeout: float):
    """Ponto único de transporte, substituível nos testes; rejeita redirects."""
    return build_opener(_SemRedirecionamento()).open(requisicao, timeout=timeout)


def _constante_json_invalida(valor: str):
    raise ValueError("Constante não permitida em JSON.")


def _objeto_sem_duplicatas(pares: list[tuple]) -> dict:
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError("Chave duplicada não permitida em JSON.")
        objeto[chave] = valor
    return objeto


def _carregar_json(texto: str | bytes):
    return json.loads(texto, parse_constant=_constante_json_invalida,
                      object_pairs_hook=_objeto_sem_duplicatas)


def _diagnostico_http(erro: HTTPError, api_key: str) -> dict:
    """Guarda apenas código, status e mensagem sanitizada; nunca headers/URL."""
    diagnostico = {"codigo": erro.code}
    try:
        documento = _carregar_json(erro.read(65536))
        detalhe = documento.get("error") if isinstance(documento, dict) else None
        if isinstance(detalhe, dict):
            status = detalhe.get("status")
            if isinstance(status, str) and re.fullmatch(r"[A-Z_]{1,80}", status):
                diagnostico["status"] = status
            mensagem = detalhe.get("message")
            if isinstance(mensagem, str):
                mensagem = mensagem.replace(api_key, "[SEGREDO_REMOVIDO]")
                mensagem = re.sub(r"AIza[A-Za-z0-9_-]+", "[SEGREDO_REMOVIDO]", mensagem)
                mensagem = re.sub(r"https?://\S+", "[URL_REMOVIDA]", mensagem)
                diagnostico["mensagem"] = mensagem[:4000]
    except (ValueError, UnicodeError, OSError):
        pass
    return {"erro_http": diagnostico}


def _post_json(corpo: dict, *, api_key: str, model: str, timeout: float) -> dict:
    try:
        dados = json.dumps(corpo, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ErroGemini("Prompt ou esquema não pôde ser serializado como JSON UTF-8.") from None
    requisicao = Request(
        _BASE_URL + model + ":generateContent",
        data=dados,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(requisicao, timeout=timeout) as resposta:
            conteudo = resposta.read()
    except HTTPError as erro:
        status = erro.code
        diagnostico = _diagnostico_http(erro, api_key)
        erro.close()
        mensagens = {
            429: "Limite de uso da Gemini API atingido (HTTP 429). Confira a cota do projeto; nenhuma repetição foi feita.",
            403: "Acesso à Gemini API negado (HTTP 403). Confira permissões, chave e disponibilidade do modelo no projeto.",
            401: "Autenticação da Gemini API recusada (HTTP 401). Confira a chave local.",
            400: "Requisição Gemini recusada (HTTP 400). Confira o contrato do esquema e a configuração do modelo.",
            404: "Modelo ou endpoint Gemini não encontrado (HTTP 404). Confira a disponibilidade do modelo no projeto.",
            503: "Modelo Gemini temporariamente indisponível (HTTP 503). Aguarde antes de tentar novamente.",
        }
        raise ErroGemini(mensagens.get(status, "A Gemini API retornou uma falha HTTP; a requisição não foi repetida."),
                         resposta=diagnostico) from None
    except (URLError, OSError, TimeoutError, ValueError):
        raise ErroGemini("Falha de conexão ou tempo limite na Gemini API; a requisição não foi repetida.") from None
    try:
        resposta_json = _carregar_json(conteudo)
    except (ValueError, UnicodeError):
        raise ErroGemini("A Gemini API retornou um documento JSON inválido.") from None
    if not isinstance(resposta_json, dict):
        raise ErroGemini("A resposta da Gemini API deve ser um objeto JSON.")
    return resposta_json


def _extrair_resultado(resposta: dict) -> dict:
    feedback = resposta.get("promptFeedback")
    bloqueio = feedback.get("blockReason") if isinstance(feedback, dict) else None
    if bloqueio and bloqueio != "BLOCK_REASON_UNSPECIFIED":
        if bloqueio == "SAFETY":
            raise ErroGemini("A Gemini API bloqueou o prompt pelo filtro SAFETY; nenhuma classificação foi aceita.")
        raise ErroGemini("A Gemini API bloqueou o prompt (promptFeedback.blockReason); nenhuma classificação foi aceita.")
    candidatos = resposta.get("candidates")
    if not isinstance(candidatos, list) or len(candidatos) != 1 or not isinstance(candidatos[0], dict):
        raise ErroGemini("A resposta Gemini não contém exatamente um candidato válido.")
    candidato = candidatos[0]
    motivo = candidato.get("finishReason")
    if motivo == "SAFETY":
        raise ErroGemini("A resposta Gemini foi bloqueada pelo filtro SAFETY; nenhuma classificação foi aceita.")
    if motivo == "MAX_TOKENS":
        raise ErroGemini("A resposta Gemini foi truncada por MAX_TOKENS; nenhuma classificação foi aceita.")
    if motivo != "STOP":
        raise ErroGemini("A resposta Gemini terminou sem STOP; nenhuma classificação foi aceita.")
    conteudo = candidato.get("content")
    partes = conteudo.get("parts") if isinstance(conteudo, dict) else None
    if not isinstance(partes, list) or any(not isinstance(parte, dict) for parte in partes):
        raise ErroGemini("A resposta Gemini não contém partes de texto válidas.")
    texto = "".join(parte["text"] for parte in partes
                    if not parte.get("thought") and isinstance(parte.get("text"), str))
    try:
        resultado = _carregar_json(texto)
    except (ValueError, UnicodeError):
        raise ErroGemini("O texto final da Gemini API não contém JSON válido.") from None
    if not isinstance(resultado, dict):
        raise ErroGemini("O texto final da Gemini API deve conter um objeto JSON.")
    return resultado


def gerar_json(prompt: str, schema: dict, *, api_key: str, model: str,
               thinking_level: str = "MEDIUM", timeout: float = 90) -> dict:
    """Executa uma chamada e retorna resultado, recibo bruto e duração.

    O chamador valida as regras de domínio e o esquema do resultado. Este cliente
    exige JSON objeto e conclusão STOP, preserva usageMetadata sem inventar zeros
    e nunca inclui chave, cabeçalhos ou requisição nos recibos ou erros. Quando a
    resposta HTTP é JSON objeto, falhas posteriores preservam o recibo no atributo
    ``ErroGemini.resposta`` e a duração em ``ErroGemini.duracao_segundos``.
    """
    _validar_chave(api_key)
    _validar_modelo(model)
    if not isinstance(prompt, str) or not prompt.strip():
        raise ErroGemini("O prompt deve ser um texto não vazio.")
    if not isinstance(schema, dict):
        raise ErroGemini("O esquema de saída deve ser um objeto JSON.")
    if not isinstance(thinking_level, str) or thinking_level not in {"LOW", "MEDIUM", "HIGH"}:
        raise ErroGemini("Nível de raciocínio inválido: use LOW, MEDIUM ou HIGH.")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ErroGemini("O tempo limite deve ser um número positivo e finito.")
    corpo = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": thinking_level},
            "responseFormat": {"text": {"mimeType": "APPLICATION_JSON", "schema": schema}},
        },
    }
    inicio = time.monotonic()
    try:
        resposta = _post_json(corpo, api_key=api_key, model=model, timeout=timeout)
    except ErroGemini as erro:
        erro.duracao_segundos = time.monotonic() - inicio
        raise
    try:
        resultado = _extrair_resultado(resposta)
    except ErroGemini as erro:
        erro.resposta = resposta
        erro.duracao_segundos = time.monotonic() - inicio
        raise
    return {"resultado": resultado, "resposta": resposta,
            "duracao_segundos": time.monotonic() - inicio}
