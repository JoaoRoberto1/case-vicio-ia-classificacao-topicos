"""Preparação opcional de vetores; nenhum encoder é usado na classificação.

Este módulo não baixa arquivos nem importa dependências de inferência ao ser
importado. O chamador verifica a procedência dos pesos e salva o cache imutável.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path


def _validar_config(config: dict) -> dict:
    limites = {
        "dimensoes": (1, 16384),
        "max_tokens": (3, 512),
        "janela_tokens": (1, 510),
        "sobreposicao_tokens": (0, 509),
        "batch_size": (1, 1024),
        "threads": (1, 1024),
        "casas_decimais": (1, 15),
    }
    valores = {}
    for nome, (minimo, maximo) in limites.items():
        valor = config.get(nome)
        if type(valor) is not int or not minimo <= valor <= maximo:
            raise ValueError(f"Configuração inválida: {nome}.")
        valores[nome] = valor
    if valores["sobreposicao_tokens"] >= valores["janela_tokens"]:
        raise ValueError("A sobreposição precisa ser menor que a janela.")
    if valores["janela_tokens"] >= valores["max_tokens"]:
        raise ValueError("A janela precisa reservar espaço para prefixo e especiais.")
    return valores


def _validar_registros(registros: list[dict]) -> list[dict]:
    vistos = set()
    ordenados = []
    for registro in registros:
        tipo = registro.get("tipo")
        identificador = registro.get("id")
        if tipo not in ("questao", "tema"):
            raise ValueError("Tipo de registro inválido.")
        if not isinstance(identificador, str) or not identificador.strip():
            raise ValueError("Identificador de registro inválido.")
        chave = tipo, identificador
        if chave in vistos:
            raise ValueError("Registro duplicado na preparação.")
        vistos.add(chave)
        texto = registro.get("texto")
        papel = registro.get("papel")
        if not isinstance(texto, str) or papel not in ("query", "passage"):
            raise ValueError("Texto ou papel inválido na preparação.")
        assinatura = hashlib.sha256(f"{papel}: {texto}".encode("utf-8")).hexdigest()
        if registro.get("texto_sha256") != assinatura:
            raise ValueError("Hash do texto diverge da entrada efetivamente codificada.")
        ordenados.append(dict(registro))
    return sorted(ordenados, key=lambda registro: (registro["tipo"], registro["id"]))


def _janelas_texto(texto: str, tokenizer, tamanho: int, sobreposicao: int):
    """Fatia pelo offset do tokenizer, sem limite de comprimento na origem."""
    codificacao = tokenizer.encode(texto, add_special_tokens=False)
    if getattr(codificacao, "overflowing", []):
        raise ValueError("O tokenizer truncou o texto antes de criar as janelas.")
    offsets = codificacao.offsets
    total = len(codificacao.ids)
    if len(offsets) != total:
        raise ValueError("Offsets e tokens possuem tamanhos incompatíveis.")
    anterior = -1
    for inicio, fim in offsets:
        if (type(inicio) is not int or type(fim) is not int
                or not 0 <= inicio <= fim <= len(texto) or inicio < anterior):
            raise ValueError("Offsets inválidos produzidos pelo tokenizer.")
        anterior = inicio
    if not total:
        return [texto], 0

    janelas = []
    inicio_token = 0
    while inicio_token < total:
        fim_token = min(inicio_token + tamanho, total)
        inicio_texto = 0 if inicio_token == 0 else offsets[inicio_token][0]
        fim_texto = len(texto) if fim_token == total else offsets[fim_token - 1][1]
        janelas.append(texto[inicio_texto:fim_texto])
        if fim_token == total:
            break
        inicio_token += tamanho - sobreposicao
    return janelas, total


def _agregar_vetores(vetores: list[list[float]], dimensoes: int, casas: int):
    if not vetores or any(len(vetor) != dimensoes for vetor in vetores):
        raise ValueError("Dimensão incompatível na agregação de janelas.")
    if any(not math.isfinite(valor) for vetor in vetores for valor in vetor):
        raise ValueError("Vetor de janela contém valores não finitos.")
    media = [
        math.fsum(vetor[indice] for vetor in vetores) / len(vetores)
        for indice in range(dimensoes)
    ]
    norma = math.sqrt(math.fsum(valor * valor for valor in media))
    if not math.isfinite(norma) or norma <= 0:
        raise ValueError("A agregação de janelas produziu um vetor nulo.")
    return [round(valor / norma, casas) or 0.0 for valor in media]


def _dependencias():
    # Esta é a única importação das bibliotecas opcionais neste módulo.
    import numpy
    import onnxruntime
    import tokenizers

    return numpy, onnxruntime, tokenizers


def _pooling_normalizado(np, estados, mascara, dimensoes: int):
    estados = np.asarray(estados, dtype=np.float32)
    mascara = np.asarray(mascara, dtype=np.float32)
    if (estados.ndim != 3 or estados.shape[:2] != mascara.shape
            or estados.shape[2] != dimensoes):
        raise ValueError("Formato inesperado na saída do encoder.")
    if not np.isfinite(estados).all():
        raise ValueError("O encoder produziu valores não finitos.")
    contagens = mascara.sum(axis=1, dtype=np.float32)
    if (contagens <= 0).any():
        raise ValueError("Uma janela não possui tokens ativos.")
    medias = (estados * mascara[..., None]).sum(axis=1, dtype=np.float32)
    medias = medias / contagens[:, None]
    normas = np.sqrt((medias * medias).sum(axis=1, dtype=np.float32))
    if not np.isfinite(normas).all() or (normas <= 0).any():
        raise ValueError("O encoder produziu um vetor nulo ou inválido.")
    return (medias / normas[:, None]).tolist()


def _inferir_lote(np, sessao, codificacoes, padding_id: int, dimensoes: int):
    comprimento = max(len(codificacao.ids) for codificacao in codificacoes)
    ids = []
    mascaras = []
    segmentos = []
    for codificacao in codificacoes:
        quantidade = len(codificacao.ids)
        tipos = list(codificacao.type_ids)
        if len(tipos) != quantidade:
            raise ValueError("Tipos de tokens incompatíveis com a codificação.")
        faltantes = comprimento - quantidade
        ids.append(list(codificacao.ids) + [padding_id] * faltantes)
        mascaras.append([1] * quantidade + [0] * faltantes)
        segmentos.append(tipos + [0] * faltantes)
    valores = {
        "input_ids": ids,
        "attention_mask": mascaras,
        "token_type_ids": segmentos,
    }
    nomes = [entrada.name for entrada in sessao.get_inputs()]
    if (not {"input_ids", "attention_mask"} <= set(nomes)
            or set(nomes) - set(valores)):
        raise ValueError("Entradas ONNX incompatíveis com o encoder esperado.")
    entradas = {
        nome: np.asarray(valores[nome], dtype=np.int64) for nome in nomes
    }
    saidas = sessao.run(None, entradas)
    if not saidas:
        raise ValueError("O encoder não produziu uma saída.")
    vetores = _pooling_normalizado(np, saidas[0], mascaras, dimensoes)
    if len(vetores) != len(codificacoes):
        raise ValueError("A saída do encoder não corresponde ao tamanho do lote.")
    return vetores


def gerar_cache(
    registros: list[dict],
    config: dict,
    modelo_path: Path,
    tokenizer_path: Path,
    progresso=None,
) -> tuple[dict, dict]:
    """Codifica somente entradas fornecidas e retorna cache e diagnóstico.

    ``progresso(processados, total)`` recebe contagens de janelas, uma vez por
    lote. Nenhum texto, identificador, timestamp ou caminho entra no diagnóstico.
    """
    parametros = _validar_config(config)
    registros = _validar_registros(registros)
    if not Path(modelo_path).is_file() or not Path(tokenizer_path).is_file():
        raise ValueError("Os arquivos locais do modelo e tokenizer são obrigatórios.")
    np, ort, tokenizers = _dependencias()
    tokenizer = tokenizers.Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    padding_id = tokenizer.token_to_id("<pad>")
    if padding_id is None:
        padding_id = tokenizer.token_to_id("[PAD]")
    if padding_id is None:
        raise ValueError("O tokenizer não declara um token de preenchimento.")

    tarefas = []
    preparados = []
    for registro in registros:
        janelas, tokens = _janelas_texto(
            registro["texto"], tokenizer, parametros["janela_tokens"],
            parametros["sobreposicao_tokens"],
        )
        indice = len(preparados)
        preparados.append({
            "registro": registro, "tokens": tokens,
            "janelas": len(janelas), "vetores": [],
        })
        for janela in janelas:
            codificacao = tokenizer.encode(
                f"{registro['papel']}: {janela}", add_special_tokens=True,
            )
            quantidade = len(codificacao.ids)
            if getattr(codificacao, "overflowing", []):
                raise ValueError("O tokenizer truncou uma janela.")
            if not 0 < quantidade <= parametros["max_tokens"]:
                raise ValueError("Janela excede o limite de tokens; truncamento recusado.")
            tarefas.append((indice, codificacao))

    opcoes = ort.SessionOptions()
    opcoes.intra_op_num_threads = parametros["threads"]
    opcoes.inter_op_num_threads = 1
    opcoes.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    sessao = ort.InferenceSession(
        str(modelo_path), sess_options=opcoes, providers=["CPUExecutionProvider"],
    )
    if sessao.get_providers() != ["CPUExecutionProvider"]:
        raise ValueError("A preparação requer exclusivamente o provedor CPU.")
    lote = parametros["batch_size"]
    for inicio in range(0, len(tarefas), lote):
        tarefas_lote = tarefas[inicio:inicio + lote]
        vetores = _inferir_lote(
            np, sessao, [codificacao for _, codificacao in tarefas_lote],
            padding_id, parametros["dimensoes"],
        )
        for (indice, _), vetor in zip(tarefas_lote, vetores):
            preparados[indice]["vetores"].append(vetor)
        if progresso is not None:
            progresso(min(inicio + lote, len(tarefas)), len(tarefas))

    cache = {
        "schema": "embeddings_e5_v1",
        "dimensoes": parametros["dimensoes"],
        "questoes": {},
        "temas": {},
    }
    for preparado in preparados:
        registro = preparado["registro"]
        destino = "questoes" if registro["tipo"] == "questao" else "temas"
        cache[destino][registro["id"]] = {
            "texto_sha256": registro["texto_sha256"],
            "vetor": _agregar_vetores(
                preparado["vetores"], parametros["dimensoes"],
                parametros["casas_decimais"],
            ),
            "tokens": preparado["tokens"],
            "janelas": preparado["janelas"],
        }
    diagnostico = {
        "registros_total": len(registros),
        "questoes_total": len(cache["questoes"]),
        "temas_total": len(cache["temas"]),
        "janelas_total": len(tarefas),
        "registros_multiplas_janelas": sum(p["janelas"] > 1 for p in preparados),
        "tokens_corpo_total": sum(p["tokens"] for p in preparados),
        "max_tokens_corpo": max((p["tokens"] for p in preparados), default=0),
        "max_tokens_janela": max((len(e.ids) for _, e in tarefas), default=0),
        "truncados": 0,
        "dimensoes": parametros["dimensoes"],
        "batch_size": lote,
        "threads": parametros["threads"],
        "casas_decimais": parametros["casas_decimais"],
        "provedor": "CPUExecutionProvider",
        "versoes_dependencias": {
            "numpy": np.__version__,
            "onnxruntime": ort.__version__,
            "tokenizers": tokenizers.__version__,
        },
    }
    return cache, diagnostico
