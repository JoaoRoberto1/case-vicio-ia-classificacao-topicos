"""Execução limitada e retomável de pilotos e lotes, sem decisões finais."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

from .gemini import ErroGemini, carregar_configuracao, gerar_json
from .piloto import esquema_resposta, validar_resposta


_ID_RE = re.compile(r"Q\d{4}", re.ASCII)
_HASH_RE = re.compile(r"[a-f0-9]{64}")
_PASTAS_PROTEGIDAS = {".git", "contexto_local", "classificacao_topicos", "tests", "docs", "prompts"}
_CAMPOS_TOKENS = ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount",
                  "cachedContentTokenCount", "totalTokenCount")


def _hash_bytes(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _canonico(objeto) -> bytes:
    return json.dumps(objeto, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _objeto_sem_duplicatas(pares):
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError("Documento JSON contém chave duplicada.")
        objeto[chave] = valor
    return objeto


def _constante_invalida(valor):
    raise ValueError("Constante inválida em JSON.")


def _json(conteudo):
    try:
        return json.loads(conteudo, object_pairs_hook=_objeto_sem_duplicatas,
                          parse_constant=_constante_invalida)
    except (ValueError, UnicodeError):
        raise ValueError("Documento JSON local inválido; confira os artefatos.") from None


def _ler(caminho: Path) -> bytes:
    if caminho.is_symlink() or not caminho.is_file():
        raise ValueError("Artefato ausente ou não é um arquivo comum.")
    return caminho.read_bytes()


def _validar_hashes(pasta: Path, hashes: dict) -> None:
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("Manifesto sem hashes de arquivos.")
    for nome, esperado in hashes.items():
        if not isinstance(nome, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", nome) or nome in {".", ".."}:
            raise ValueError("Nome de arquivo inválido no manifesto.")
        if not isinstance(esperado, str) or not _HASH_RE.fullmatch(esperado):
            raise ValueError("Hash inválido no manifesto.")
        if _hash_bytes(_ler(pasta / nome)) != esperado:
            raise ValueError("Hash de artefato divergente; regenere a preparação ou o piloto.")


def _raiz_fontes(preparacao: Path, hashes: dict) -> Path:
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("Manifesto de preparação sem fontes rastreáveis.")
    # O manifesto v1 guarda nomes, não caminhos absolutos. Preferir a árvore local
    # da preparação; aceitar a raiz do pacote para saídas em outra unidade/pasta.
    candidatos = [*preparacao.parents, Path(__file__).resolve().parents[1]]
    for raiz in dict.fromkeys(candidatos):
        if all(isinstance(nome, str) and (raiz / nome).is_file() for nome in hashes):
            _validar_hashes(raiz, hashes)
            return raiz
    raise ValueError("Não foi possível localizar as fontes originais da preparação.")


def _validar_entradas(piloto: Path, preparacao: Path, *,
                      procedimento_esperado: str | None = None) -> tuple[list[dict], dict, dict, str, Path]:
    manifesto_preparacao_bytes = _ler(preparacao / "manifesto.json")
    manifesto_preparacao = _json(manifesto_preparacao_bytes)
    nomes_manifestos = {"manifesto_piloto.json": "piloto-v1", "manifesto_lote.json": "lote-v1"}
    presentes = [nome for nome in nomes_manifestos
                 if (piloto / nome).exists() or (piloto / nome).is_symlink()]
    if len(presentes) != 1:
        raise ValueError("A pasta de entradas deve conter exatamente um manifesto de piloto ou lote.")
    nome_manifesto = presentes[0]
    procedimento = nomes_manifestos[nome_manifesto]
    if procedimento_esperado is not None and procedimento != procedimento_esperado:
        raise ValueError("O manifesto não corresponde ao tipo de execução solicitado (piloto ou lote).")
    manifesto_piloto = _json(_ler(piloto / nome_manifesto))
    if not isinstance(manifesto_preparacao, dict) or not isinstance(manifesto_piloto, dict):
        raise ValueError("Manifestos devem conter objetos JSON.")
    if (manifesto_preparacao.get("schema_version") != 1 or manifesto_preparacao.get("procedimento") != "preparacao-v1"
            or manifesto_piloto.get("schema_version") != 1 or manifesto_piloto.get("procedimento") != procedimento):
        raise ValueError("Versão ou procedimento dos manifestos não é suportado.")
    produtos = manifesto_preparacao.get("produtos_sha256")
    _validar_hashes(preparacao, produtos)
    if not {"questoes_preparadas.jsonl", "temas_preparados.json"}.issubset(produtos):
        raise ValueError("Manifesto de preparação não cobre questões e taxonomia.")
    raiz = _raiz_fontes(preparacao, manifesto_preparacao.get("fontes_sha256"))
    hash_preparacao = _hash_bytes(manifesto_preparacao_bytes)
    if manifesto_piloto.get("preparacao_sha256") != hash_preparacao:
        raise ValueError("O piloto foi gerado a partir de outra preparação.")
    if manifesto_piloto.get("preparacao_produtos_sha256") != produtos:
        raise ValueError("Os hashes de preparação e piloto são incompatíveis.")
    _validar_hashes(piloto, manifesto_piloto.get("produtos_sha256"))
    if "entradas.jsonl" not in manifesto_piloto["produtos_sha256"]:
        raise ValueError("Manifesto do piloto não cobre entradas.jsonl.")
    ids = manifesto_piloto.get("ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not _ID_RE.fullmatch(i) for i in ids):
        raise ValueError("IDs inválidos no manifesto do piloto.")
    if len(ids) != len(set(ids)):
        raise ValueError("IDs duplicados no manifesto do piloto.")
    entradas = []
    # split em LF preserva U+2028 e U+0085 que podem ocorrer dentro dos textos.
    for linha in _ler(piloto / "entradas.jsonl").decode("utf-8-sig").split("\n"):
        if not linha.strip():
            continue
        item = _json(linha)
        if not isinstance(item, dict) or set(item) != {"id", "prompt", "sha256_prompt"}:
            raise ValueError("Entrada do piloto contém campos inesperados.")
        if not isinstance(item["id"], str) or not _ID_RE.fullmatch(item["id"]):
            raise ValueError("ID de questão inválido na entrada do piloto.")
        if not isinstance(item["prompt"], str) or not item["prompt"].strip():
            raise ValueError("Prompt vazio ou inválido no piloto.")
        if _hash_bytes(item["prompt"].encode("utf-8")) != item["sha256_prompt"]:
            raise ValueError("Hash do prompt divergente; regenere o piloto.")
        entradas.append(item)
    if [item["id"] for item in entradas] != ids:
        raise ValueError("IDs ou ordem de entradas divergem do manifesto do piloto.")
    questoes = [_json(linha) for linha in _ler(preparacao / "questoes_preparadas.jsonl").decode("utf-8-sig").split("\n") if linha.strip()]
    if any(not isinstance(q, dict) or not isinstance(q.get("id"), str) for q in questoes):
        raise ValueError("Questões preparadas inválidas.")
    questoes_por_id = {q["id"]: q for q in questoes}
    if len(questoes_por_id) != len(questoes):
        raise ValueError("Questões preparadas contêm IDs duplicados.")
    if not set(ids).issubset(questoes_por_id):
        raise ValueError("O piloto contém questões ausentes na preparação.")
    if procedimento == "lote-v1" and set(ids) != set(questoes_por_id):
        raise ValueError("O lote deve conter todas as questões da preparação, sem omissões.")
    temas = _json(_ler(preparacao / "temas_preparados.json"))
    if not isinstance(temas, list) or not temas or any(not isinstance(t, dict) or not isinstance(t.get("tema_id"), str) for t in temas):
        raise ValueError("Taxonomia preparada inválida.")
    temas_por_id = {t["tema_id"]: t for t in temas}
    if len(temas_por_id) != len(temas):
        raise ValueError("Taxonomia preparada contém IDs duplicados.")
    return entradas, temas_por_id, questoes_por_id, hash_preparacao, raiz


def _validar_saida(saida: Path, *, piloto: Path, preparacao: Path, raiz: Path) -> Path:
    caminho = saida.absolute()
    for parte in (caminho, *caminho.parents):
        if parte.is_symlink() or (hasattr(parte, "is_junction") and parte.is_junction()):
            raise ValueError("A saída e seus ancestrais não podem ser links ou junções.")
    saida = caminho.resolve()
    if any(parte.casefold() in _PASTAS_PROTEGIDAS for parte in saida.parts):
        raise ValueError("A saída aponta para uma pasta protegida.")
    if saida == raiz or saida in raiz.parents:
        raise ValueError("A saída não pode ser a raiz dos materiais ou um ancestral.")
    for entrada in (piloto, preparacao):
        if saida == entrada or saida in entrada.parents or entrada in saida.parents:
            raise ValueError("A saída deve ser separada das pastas de preparação e piloto.")
    if saida.exists() and not saida.is_dir():
        raise ValueError("A saída deve ser uma pasta.")
    return saida


def _fingerprint(entrada: dict, model: str, schema_hash: str, preparacao_hash: str) -> str:
    return _hash_bytes(_canonico({"model": model, "sha256_prompt": entrada["sha256_prompt"],
                                  "sha256_schema": schema_hash, "sha256_preparacao": preparacao_hash,
                                  "thinking_level": "MEDIUM"}))


def _validar_evidencia(sugestao: dict, questao: dict) -> str:
    textos = [questao.get("enunciado"), questao.get("comando")]
    alternativas = questao.get("alternativas")
    if isinstance(alternativas, dict):
        textos.extend(alternativas.values())
    if any(isinstance(texto, str) and sugestao["evidencia"] in texto for texto in textos):
        return "literal"
    # Variações de caixa e espaços não alteram as palavras do trecho. Não
    # normalizar acentos, pontuação ou OCR e não aceitar texto aproximado.
    evidencia = " ".join(sugestao["evidencia"].split()).casefold()
    if evidencia and any(isinstance(texto, str) and evidencia in " ".join(texto.split()).casefold()
                         for texto in textos):
        return "caixa_e_espacos_normalizados"
    raise ValueError("A evidência não reproduz um trecho literal da questão, mesmo normalizando caixa e espaços.")


def _validar_cache(caminho: Path, entrada: dict, model: str, schema_hash: str,
                   preparacao_hash: str, temas_por_id: dict, questao: dict) -> dict:
    registro = _json(_ler(caminho))
    if not isinstance(registro, dict):
        raise ValueError("Recibo local inválido; use uma nova pasta de saída.")
    esperado = _fingerprint(entrada, model, schema_hash, preparacao_hash)
    if (registro.get("fingerprint") != esperado or registro.get("id") != entrada["id"]
            or registro.get("model") != model or registro.get("sha256_prompt") != entrada["sha256_prompt"]
            or registro.get("sha256_schema") != schema_hash):
        raise ValueError("Cache pertence a outro modelo, prompt ou esquema; use uma nova pasta de saída.")
    sem_hash = {k: v for k, v in registro.items() if k != "sha256_registro"}
    if registro.get("sha256_registro") != _hash_bytes(_canonico(sem_hash)):
        raise ValueError("Checksum de recibo divergente; use uma nova pasta de saída.")
    if registro.get("status") == "sucesso":
        try:
            sugestao = validar_resposta(registro.get("sugestao"), entrada["id"], temas_por_id)
            _validar_evidencia(sugestao, questao)
        except Exception:
            raise ValueError("Sugestão em cache é inválida; use uma nova pasta de saída.") from None
    elif registro.get("status") != "erro":
        raise ValueError("Status de recibo inválido; use uma nova pasta de saída.")
    return registro


def _gravar_atomico(caminho: Path, registro: dict) -> None:
    if caminho.is_symlink() or (caminho.exists() and not caminho.is_file()):
        raise ValueError("Destino de recibo não é um arquivo comum.")
    registro.pop("sha256_registro", None)
    registro["sha256_registro"] = _hash_bytes(_canonico(registro))
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".recibo-", suffix=".tmp",
                                         dir=caminho.parent, delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(json.dumps(registro, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _resumo(registros: dict, total: int, cache: int, novas: int, erro_id: str | None,
            revalidacoes: dict | None = None) -> dict:
    from .revalidacao import status_efetivo
    revalidacoes = revalidacoes or {}
    tokens, informados = {}, {}
    tentativas = []
    for registro in registros.values():
        tentativas.extend(registro.get("tentativas_anteriores", []))
        tentativas.append(registro)
    for registro in tentativas:
        usage = registro.get("usage_metadata")
        if not isinstance(usage, dict):
            continue
        for campo in _CAMPOS_TOKENS:
            valor = usage.get(campo)
            if type(valor) is int and valor >= 0:
                tokens[campo] = tokens.get(campo, 0) + valor
                informados[campo] = informados.get(campo, 0) + 1
    sucesso = sum(status_efetivo(r, revalidacoes.get(i)) == "sucesso" for i, r in registros.items())
    erros_validacao = sorted(identificador for identificador, registro in registros.items()
                             if status_efetivo(registro, revalidacoes.get(identificador)) == "erro"
                             and registro.get("erro", {}).get("tipo") == "ErroValidacaoLocal")
    return {"total": total, "cache": cache, "novas": novas, "sucesso": sucesso,
            "pendencia": total - sucesso, "parou_em_erro": erro_id,
            "erros_validacao_ids": erros_validacao,
            "revalidacoes_ids": sorted(revalidacoes),
            "concluido_com_falhas": bool(erros_validacao) and erro_id is None,
            "tentativas_registradas": len(tentativas),
            "tokens_observados": tokens, "tokens_registros_informados": informados}


def _executar(piloto: Path, preparacao: Path, saida: Path, *, tipo: str,
              limite_maximo: int, env_path: Path | None, limite: int,
              intervalo_segundos: float, continuar_erros_validacao: bool = False,
              ids_selecionados: list[str] | None = None) -> dict:
    """Núcleo compartilhado; o tipo de conjunto não altera a identidade do recibo."""
    from .revalidacao import carregar_revalidacao, status_efetivo
    piloto, preparacao = Path(piloto).resolve(), Path(preparacao).resolve()
    entradas, temas_por_id, questoes_por_id, preparacao_hash, raiz = _validar_entradas(
        piloto, preparacao, procedimento_esperado=f"{tipo}-v1")
    entradas_escopo = entradas
    if ids_selecionados is not None:
        if (not isinstance(ids_selecionados, list) or not ids_selecionados
                or any(not isinstance(i, str) or not _ID_RE.fullmatch(i) for i in ids_selecionados)):
            raise ValueError("ids_selecionados deve ser uma lista não vazia de IDs válidos.")
        ids_escopo = set(ids_selecionados)
        if len(ids_escopo) != len(ids_selecionados):
            raise ValueError("ids_selecionados contém IDs duplicados.")
        if not ids_escopo.issubset(item["id"] for item in entradas):
            raise ValueError("ids_selecionados contém IDs ausentes do lote.")
        entradas_escopo = [item for item in entradas if item["id"] in ids_escopo]
    if type(limite) is not int or not 1 <= limite <= min(limite_maximo, len(entradas_escopo)):
        conjunto = "escopo selecionado" if ids_selecionados is not None else tipo
        raise ValueError(f"O limite deve estar entre 1 e {limite_maximo}, sem exceder o tamanho do {conjunto}.")
    if type(continuar_erros_validacao) is not bool:
        raise ValueError("continuar_erros_validacao deve ser booleano.")
    if isinstance(intervalo_segundos, bool) or not isinstance(intervalo_segundos, (int, float)) or not math.isfinite(intervalo_segundos) or intervalo_segundos < 0:
        raise ValueError("O intervalo deve ser um número finito não negativo.")
    saida = _validar_saida(Path(saida), piloto=piloto, preparacao=preparacao, raiz=raiz)
    config = carregar_configuracao(env_path)
    schema = esquema_resposta()
    schema_hash = _hash_bytes(_canonico(schema))
    saida.mkdir(parents=True, exist_ok=True)
    permitidos = {item["id"] + ".json" for item in entradas}
    if tipo == "lote":
        permitidos.update(item["id"] + ".revalidacao.json" for item in entradas)
    for caminho in saida.iterdir():
        if caminho.name not in permitidos or caminho.is_symlink() or not caminho.is_file():
            raise ValueError("A saída contém arquivos incompatíveis ou uma execução ativa; use outra pasta.")
        if caminho.name.endswith(".revalidacao.json"):
            original = saida / (caminho.name.removesuffix(".revalidacao.json") + ".json")
            if not original.is_file() or original.is_symlink():
                raise ValueError("Revalidação sem recibo original correspondente.")
    # Exclusão mútua evita chamadas duplicadas entre dois processos locais.
    lock = saida / ".execucao.lock"
    try:
        arquivo_lock = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Existe outra execução nesta pasta; aguarde sua conclusão.") from None
    registros = {}
    revalidacoes = {}
    novas = cache = 0
    erro_id = None
    try:
        with arquivo_lock:
            arquivo_lock.write(datetime.now(timezone.utc).isoformat())
        for entrada in entradas:
            caminho = saida / (entrada["id"] + ".json")
            if caminho.exists():
                registros[entrada["id"]] = _validar_cache(caminho, entrada, config["model"], schema_hash, preparacao_hash, temas_por_id, questoes_por_id[entrada["id"]])
                if tipo == "lote":
                    revalidacao = carregar_revalidacao(caminho, registros[entrada["id"]], entrada,
                                                       config["model"], schema_hash, preparacao_hash,
                                                       temas_por_id, questoes_por_id[entrada["id"]])
                    if revalidacao is not None:
                        revalidacoes[entrada["id"]] = revalidacao
        # Validar toda a pasta continua obrigatório. Só o escopo solicitado
        # participa das chamadas, das pendências e da contagem de consumo.
        if ids_selecionados is not None:
            registros = {i: r for i, r in registros.items() if i in ids_escopo}
            revalidacoes = {i: r for i, r in revalidacoes.items() if i in ids_escopo}
        cache = sum(status_efetivo(r, revalidacoes.get(i)) == "sucesso" for i, r in registros.items())
        for entrada in entradas_escopo:
            identificador = entrada["id"]
            if identificador in registros and status_efetivo(registros[identificador], revalidacoes.get(identificador)) == "sucesso":
                continue
            if novas >= limite:
                break
            if novas:
                time.sleep(intervalo_segundos)
            registro = {"schema_version": 1, "id": identificador, "model": config["model"],
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "sha256_prompt": entrada["sha256_prompt"], "sha256_schema": schema_hash,
                        "sha256_preparacao": preparacao_hash, "thinking_level": "MEDIUM",
                        "fingerprint": _fingerprint(entrada, config["model"], schema_hash, preparacao_hash)}
            anterior = registros.get(identificador)
            if anterior is not None:
                # Histórico plano: cada tentativa anterior mantém seu recibo e
                # consumo uma única vez. Seu checksum cobre a tentativa isolada.
                historico = list(anterior.get("tentativas_anteriores", []))
                tentativa = {k: v for k, v in anterior.items()
                             if k not in {"tentativas_anteriores", "sha256_registro"}}
                tentativa["sha256_registro"] = _hash_bytes(_canonico(tentativa))
                historico.append(tentativa)
                registro["tentativas_anteriores"] = historico
            registro["numero_tentativa"] = 1 + len(registro.get("tentativas_anteriores", []))
            novas += 1
            inicio = time.monotonic()
            try:
                obtido = gerar_json(entrada["prompt"], schema, api_key=config["api_key"], model=config["model"])
                registro["resposta_bruta"] = obtido["resposta"]
                registro["duracao_segundos"] = obtido["duracao_segundos"]
                if "usageMetadata" in obtido["resposta"]:
                    registro["usage_metadata"] = obtido["resposta"]["usageMetadata"]
                sugestao = validar_resposta(obtido["resultado"], identificador, temas_por_id)
                registro["validacao_evidencia"] = _validar_evidencia(sugestao, questoes_por_id[identificador])
                registro["sugestao"] = sugestao
                registro["status"] = "sucesso"
            except Exception as erro:
                registro["status"] = "erro"
                registro.setdefault("duracao_segundos", time.monotonic() - inicio)
                if isinstance(erro, ErroGemini):
                    mensagem = str(erro).replace(config["api_key"], "[SEGREDO_REMOVIDO]")
                    tipo_erro = "ErroGemini"
                    if erro.resposta is not None:
                        registro["resposta_bruta"] = erro.resposta
                        if "usageMetadata" in erro.resposta:
                            registro["usage_metadata"] = erro.resposta["usageMetadata"]
                    if erro.duracao_segundos is not None:
                        registro["duracao_segundos"] = erro.duracao_segundos
                else:
                    mensagem = "Falha ao validar ou processar a resposta localmente; confira o recibo salvo."
                    tipo_erro = "ErroValidacaoLocal"
                registro["erro"] = {"tipo": tipo_erro, "mensagem": mensagem}
                if tipo_erro != "ErroValidacaoLocal" or not continuar_erros_validacao:
                    erro_id = identificador
            _gravar_atomico(saida / (identificador + ".json"), registro)
            registros[identificador] = registro
            if erro_id:
                break
        resumo = _resumo(registros, len(entradas_escopo), cache, novas, erro_id, revalidacoes)
        if ids_selecionados is not None:
            resumo.update(total_lote=len(entradas), total_escopo=len(entradas_escopo),
                          ids_selecionados=[item["id"] for item in entradas_escopo])
        return resumo
    finally:
        lock.unlink(missing_ok=True)


def executar_piloto(piloto: Path, preparacao: Path, saida: Path, *,
                    env_path: Path | None = None, limite: int = 1,
                    intervalo_segundos: float = 10.0) -> dict:
    """Executa no máximo 20 novas chamadas do piloto e para na primeira falha.

    O padrão é uma chamada. Sucessos são reutilizados após validar identidade,
    checksum e sugestão. Erros podem ser tentados novamente, mantendo o histórico.
    O resumo soma apenas tokens informados, inclusive cache e tentativas anteriores;
    campos ausentes não viram zero. Aceita somente manifesto_piloto.json.
    """
    return _executar(piloto, preparacao, saida, tipo="piloto", limite_maximo=20,
                     env_path=env_path, limite=limite, intervalo_segundos=intervalo_segundos)


def executar_lote(lote: Path, preparacao: Path, saida: Path, *,
                  env_path: Path | None = None, limite: int = 1,
                  intervalo_segundos: float = 10.0,
                  continuar_erros_validacao: bool = False,
                  ids_selecionados: list[str] | None = None) -> dict:
    """Executa no máximo 500 novas chamadas de um lote completo; padrão de uma.

    Exige manifesto_lote.json e todos os IDs da preparação. Mantém o contrato de
    recibos do piloto: sucessos compatíveis são reutilizáveis sem mudar fingerprint,
    erros preservam tentativas e consumo, e a primeira falha interrompe a execução
    por padrão. A opção continuar_erros_validacao avança após falhas locais sem
    tentar o mesmo ID novamente nesta chamada; erros Gemini sempre interrompem.
    concluido_com_falhas indica término sem interrupção com erros locais ainda
    presentes, inclusive quando o limite solicitado cobre só parte do conjunto.
    Revalidações offline válidas são reutilizadas e identificadas no resumo;
    seus recibos originais continuam sendo a única fonte de contagem de chamadas.
    ids_selecionados restringe as chamadas a uma lista não vazia, sem duplicatas,
    preservando a ordem do manifesto completo e a validação de toda a pasta.
    Com seleção, total e demais métricas referem-se ao escopo selecionado;
    total_lote, total_escopo e ids_selecionados explicitam essa delimitação.
    """
    return _executar(lote, preparacao, saida, tipo="lote", limite_maximo=500,
                     env_path=env_path, limite=limite, intervalo_segundos=intervalo_segundos,
                     continuar_erros_validacao=continuar_erros_validacao,
                     ids_selecionados=ids_selecionados)
