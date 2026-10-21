"""Preparação opcional E5-large INT8; a decisão consome apenas o cache JSON.

Nenhum texto de questão, rótulo ou classificação é impresso. O modelo local
gera vetores, sem escolher temas. O download é uma ação separada e explícita.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

from classificacao_catalogo.catalogo import ARQUIVOS, carregar
from classificacao_experimentos.contexto import assinar, conferir_assinaturas
from classificacao_experimentos.entradas import construir_registros, validar_cache
from classificacao_topicos.pipeline import _json

CONFIG = "config/modulo8/embeddings_large.json"
PASTA = "artefatos/embeddings-e5-large-m8"
FONTES = ARQUIVOS + [
    "config/modulo7/preparacao_catalogo.json",
    "classificacao_catalogo/catalogo.py",
    "classificacao_experimentos/entradas.py",
    "classificacao_experimentos/preparacao_embeddings.py",
    "classificacao_precisao/preparar_large.py",
    "artefatos/preparacao/questoes_preparadas.jsonl",
    "artefatos/preparacao/temas_preparados.json",
    "config/modulo8/protocolo.json",
    CONFIG,
]


def _ler(raiz: Path, nome: str):
    return json.loads((raiz / nome).read_text(encoding="utf-8"))


def _sha_arquivo(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _salvar_imutavel(caminho: Path, conteudo: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        if caminho.read_bytes() != conteudo:
            raise ValueError("Artefato existente diferente: crie outra versão.")
        return
    with caminho.open("xb") as arquivo:
        arquivo.write(conteudo)


def baixar(raiz: Path):
    """Baixa somente dois arquivos públicos fixados e valida tamanho/hash."""
    config = _ler(raiz, CONFIG)
    pasta = raiz / ".cache-modelos/e5-large"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, esperado in config["arquivos"].items():
        destino = pasta / nome
        if destino.exists():
            if destino.stat().st_size != esperado["bytes"] or _sha_arquivo(destino) != esperado["sha256"]:
                raise ValueError("Arquivo local existente diverge do encoder fixado.")
            continue
        temporario = destino.with_suffix(destino.suffix + ".download")
        url = (f"{config['origem']}/resolve/{config['revisao']}/"
               f"{esperado['caminho_remoto']}?download=true")
        resumo = hashlib.sha256()
        recebidos = 0
        ultima = time.monotonic()
        with urllib.request.urlopen(url, timeout=90) as resposta, temporario.open("wb") as arquivo:
            while bloco := resposta.read(1024 * 1024):
                recebidos += len(bloco)
                if recebidos > esperado["bytes"]:
                    raise ValueError("Download excedeu o tamanho previamente fixado.")
                arquivo.write(bloco)
                resumo.update(bloco)
                if time.monotonic() - ultima >= 25:
                    print(f"Download: {recebidos}/{esperado['bytes']} bytes", flush=True)
                    ultima = time.monotonic()
        if recebidos != esperado["bytes"] or resumo.hexdigest() != esperado["sha256"]:
            raise ValueError("Download diverge do tamanho/hash oficial fixado.")
        temporario.rename(destino)
        print(f"Arquivo validado: {nome}, {recebidos} bytes", flush=True)


def _memoria() -> dict:
    if sys.platform != "win32":
        return {}
    class Estado(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (nome, ctypes.c_ulonglong) for nome in
            ("total_phys", "avail_phys", "total_page", "avail_page",
             "total_virtual", "avail_virtual", "avail_extended")]
    estado = Estado()
    estado.length = ctypes.sizeof(estado)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
        raise OSError("Não foi possível consultar a memória disponível.")
    return {"ram_livre_bytes": int(estado.avail_phys),
            "comprometimento_livre_bytes": int(estado.avail_page)}


def _fontes_m7(raiz: Path) -> dict:
    """Confere hashes dos insumos sem abrir rótulos ou predições anteriores."""
    manifesto = _ler(raiz, "artefatos/catalogo-m7-embeddings/manifesto.json")
    fixadas = manifesto["fontes_sha256"]
    checkpoint = _ler(raiz, "artefatos/checkpoints/modulo7.json")
    checkpoint_fontes = checkpoint["artefatos_sha256"]
    conferir_assinaturas(raiz, {p: checkpoint_fontes[p] for p in ARQUIVOS + [
        "config/modulo7/preparacao_catalogo.json", "classificacao_catalogo/catalogo.py",
        "artefatos/catalogo-m7-embeddings/manifesto.json"]})
    selecionadas = {p: fixadas[p] for p in ARQUIVOS + [
        "classificacao_catalogo/catalogo.py", "artefatos/preparacao/temas_preparados.json"]}
    conferir_assinaturas(raiz, selecionadas)
    m1 = _ler(raiz, "artefatos/preparacao/manifesto.json")
    # Os arquivos do M1 também são conferidos pelo seu manifesto de produtos.
    produtos = m1.get("produtos_sha256", {})
    for nome in ("questoes_preparadas.jsonl", "temas_preparados.json"):
        if nome not in produtos:
            raise ValueError("Manifesto M1 não fixa as entradas de vetorização.")
        selecionadas["artefatos/preparacao/" + nome] = produtos[nome]
    conferir_assinaturas(raiz, selecionadas)
    return selecionadas


def _registros(raiz: Path) -> tuple[list[dict], dict]:
    fontes = _fontes_m7(raiz)
    temas = _ler(raiz, "artefatos/preparacao/temas_preparados.json")
    taxonomia = carregar(raiz, {"registros": temas,
                              "por_id": {t["tema_id"]: t for t in temas}})
    with (raiz / "artefatos/preparacao/questoes_preparadas.jsonl").open(encoding="utf-8") as arquivo:
        questoes = [json.loads(linha) for linha in arquivo]
    registros = construir_registros(questoes, taxonomia["registros"], {q["id"] for q in questoes})
    if len(questoes) != 659 or len(registros) != 1030:
        raise ValueError("Escopo diverge das 659 questões e 371 temas fixados.")
    return registros, fontes


def selecionar_piloto(registros: list[dict]) -> list[dict]:
    saida = []
    for tipo in ("questao", "tema"):
        candidatos = [r for r in registros if r["tipo"] == tipo]
        candidatos.sort(key=lambda r: hashlib.sha256(f"{tipo}:{r['id']}".encode()).digest())
        saida.extend(candidatos[:5])
    return saida


def _salvar_checkpoint(pasta: Path, nome: str, dados: bytes) -> None:
    pasta = pasta.resolve()
    final = (pasta / nome).resolve()
    temporario = (pasta / (nome + ".tmp")).resolve()
    if final.parent != pasta or temporario.parent != pasta:
        raise ValueError("Checkpoint fora da pasta de preparação.")
    temporario.write_bytes(dados)
    temporario.replace(final)


def _gerar_streaming(registros, config, modelo, pasta_checkpoint, fontes, progresso):
    """Reusa tokenização/pooling M3, libera arena e salva cada vetor concluído."""
    from classificacao_experimentos.preparacao_embeddings import (
        _agregar_vetores, _dependencias, _inferir_lote, _janelas_texto,
        _validar_config, _validar_registros,
    )
    parametros = _validar_config(config["preparacao"])
    registros = _validar_registros(registros)
    identidade = {"configuracao_sha256": hashlib.sha256(_json(config)).hexdigest(),
                  "fontes_sha256": fontes,
                  "entradas_sha256": hashlib.sha256(_json([
                      {k: r[k] for k in ("tipo", "id", "papel", "texto_sha256")}
                      for r in registros])).hexdigest()}
    pasta_checkpoint.mkdir(parents=True, exist_ok=True)
    indice_path = pasta_checkpoint / "indice.json"
    if indice_path.exists():
        indice = json.loads(indice_path.read_text(encoding="utf-8"))
        if indice.get("identidade") != identidade:
            raise ValueError("Checkpoint pertence a outras entradas/configuração/implementação.")
    else:
        indice = {"schema": "checkpoint_encoder_large_m8_v1", "identidade": identidade,
                  "registros_sha256": {}}
        _salvar_checkpoint(pasta_checkpoint, "indice.json", _json(indice))
    np, ort, tokenizers = _dependencias()
    tokenizer = tokenizers.Tokenizer.from_file(str(modelo / "tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    padding_id = tokenizer.token_to_id("<pad>")
    if padding_id is None:
        padding_id = tokenizer.token_to_id("[PAD]")
    if padding_id is None:
        raise ValueError("Tokenizer não declara padding.")
    opcoes = ort.SessionOptions()
    opcoes.intra_op_num_threads = parametros["threads"]
    opcoes.inter_op_num_threads = 1
    opcoes.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opcoes.enable_cpu_mem_arena = config["sessao_onnx"]["enable_cpu_mem_arena"]
    opcoes.enable_mem_pattern = config["sessao_onnx"]["enable_mem_pattern"]
    sessao = ort.InferenceSession(str(modelo / "modelo.onnx"), sess_options=opcoes,
                                 providers=["CPUExecutionProvider"])
    if sessao.get_providers() != ["CPUExecutionProvider"]:
        raise ValueError("Encoder requer exclusivamente CPU.")
    cache = {"schema": "embeddings_e5_v1", "dimensoes": 1024, "questoes": {}, "temas": {}}
    max_janela = 0
    janelas_total = 0
    reutilizados = 0
    for n, registro in enumerate(registros, 1):
        chave = hashlib.sha256(f"{registro['tipo']}:{registro['id']}".encode()).hexdigest()
        nome = chave + ".json"
        campo = "questoes" if registro["tipo"] == "questao" else "temas"
        janelas, tokens = _janelas_texto(registro["texto"], tokenizer,
                                       parametros["janela_tokens"], parametros["sobreposicao_tokens"])
        codificacoes = [tokenizer.encode(f"{registro['papel']}: {janela}", add_special_tokens=True)
                        for janela in janelas]
        for codificacao in codificacoes:
            if (getattr(codificacao, "overflowing", []) or
                    not 0 < len(codificacao.ids) <= parametros["max_tokens"]):
                raise ValueError("Janela inválida: truncamento recusado.")
        max_janela = max(max_janela, *(len(c.ids) for c in codificacoes))
        janelas_total += len(codificacoes)
        if nome in indice["registros_sha256"]:
            dados = (pasta_checkpoint / nome).read_bytes()
            if hashlib.sha256(dados).hexdigest() != indice["registros_sha256"][nome]:
                raise ValueError("Vetor parcial adulterado.")
            item = json.loads(dados)
            reutilizados += 1
        else:
            vetores = []
            for codificacao in codificacoes:
                vetores.extend(_inferir_lote(np, sessao, [codificacao], padding_id, 1024))
            item = {"texto_sha256": registro["texto_sha256"],
                    "vetor": _agregar_vetores(vetores, 1024, parametros["casas_decimais"]),
                    "tokens": tokens, "janelas": len(codificacoes)}
            dados = _json(item)
            _salvar_checkpoint(pasta_checkpoint, nome, dados)
            indice["registros_sha256"][nome] = hashlib.sha256(dados).hexdigest()
            _salvar_checkpoint(pasta_checkpoint, "indice.json", _json(indice))
        parcial = {"schema": "embeddings_e5_v1", "dimensoes": 1024,
                   "questoes": {}, "temas": {}}
        parcial[campo][registro["id"]] = item
        validar_cache(parcial, [registro], dimensoes=1024)
        if item["tokens"] != tokens or item["janelas"] != len(codificacoes):
            raise ValueError("Contagens do checkpoint divergem da tokenização fixada.")
        cache[campo][registro["id"]] = item
        progresso(n, len(registros))
    del sessao
    gc.collect()
    todos = list(cache["questoes"].values()) + list(cache["temas"].values())
    diagnostico = {"registros_total": len(registros), "questoes_total": len(cache["questoes"]),
                   "temas_total": len(cache["temas"]), "janelas_total": janelas_total,
                   "registros_multiplas_janelas": sum(x["janelas"] > 1 for x in todos),
                   "tokens_corpo_total": sum(x["tokens"] for x in todos),
                   "max_tokens_corpo": max(x["tokens"] for x in todos),
                   "max_tokens_janela": max_janela, "truncados": 0, "dimensoes": 1024,
                   "batch_size": 1, "threads": parametros["threads"],
                   "casas_decimais": parametros["casas_decimais"], "provedor": "CPUExecutionProvider",
                   "versoes_dependencias": {"numpy": np.__version__, "onnxruntime": ort.__version__,
                                            "tokenizers": tokenizers.__version__}}
    return cache, diagnostico, reutilizados


def executar(raiz: Path, piloto: bool = False):
    config = _ler(raiz, CONFIG)
    registros, fixadas = _registros(raiz)
    if piloto:
        registros = selecionar_piloto(registros)
    inicio = time.monotonic()
    memoria_inicio = _memoria()
    minima_ram = memoria_inicio.get("ram_livre_bytes", 0)
    minima_commit = memoria_inicio.get("comprometimento_livre_bytes", 0)
    if memoria_inicio and (minima_ram < 200 * 1024**2 or minima_commit < 1800 * 1024**2):
        raise MemoryError("Memória disponível insuficiente para iniciar o encoder INT8.")
    modelo = raiz / ".cache-modelos/e5-large"
    for nome, esperado in config["arquivos"].items():
        caminho = modelo / nome
        if caminho.stat().st_size != esperado["bytes"] or _sha_arquivo(caminho) != esperado["sha256"]:
            raise ValueError("Pesos ou tokenizer divergem da revisão oficial fixada.")
    ultima = [time.monotonic()]
    def progresso(n, total):
        nonlocal minima_ram, minima_commit
        memoria = _memoria()
        if memoria:
            minima_ram = min(minima_ram, memoria["ram_livre_bytes"])
            minima_commit = min(minima_commit, memoria["comprometimento_livre_bytes"])
            if memoria["ram_livre_bytes"] < 200 * 1024**2 or memoria["comprometimento_livre_bytes"] < 512 * 1024**2:
                raise MemoryError("Preparação interrompida: pressão de memória acima do limite.")
        if n == total or time.monotonic() - ultima[0] >= 25:
            print(f"Registros codificados: {n}/{total}; segundos: {time.monotonic()-inicio:.1f}", flush=True)
            ultima[0] = time.monotonic()
    fontes = assinar(raiz, FONTES)
    pasta_checkpoint = modelo / ("checkpoint-piloto-memoria" if piloto else "checkpoint-completo")
    cache, diagnostico, reutilizados = _gerar_streaming(registros, config, modelo,
                                                      pasta_checkpoint, fontes, progresso)
    validar_cache(cache, registros, dimensoes=1024)
    dados = _json(cache)
    manifesto = {
        "schema": "cache_large_int8_m8_v1",
        "configuracao": config,
        "fontes_sha256": fontes,
        "fontes_m1_m7_conferidas_sha256": fixadas,
        "diagnostico": diagnostico,
        "produtos_sha256": {"vetores.json": hashlib.sha256(dados).hexdigest()},
        "llm_decide_classificacoes": False,
        "rotulos_ou_predicoes_abertos": False,
        "encoder_executado_somente_na_preparacao": True,
        "piloto": piloto,
    }
    medicao = {"schema": "execucao_encoder_large_m8_v1", "piloto": piloto,
               "segundos": round(time.monotonic() - inicio, 3),
               "memoria_inicio": memoria_inicio, "memoria_final": _memoria(),
               "minima_ram_livre_bytes": minima_ram,
               "minimo_comprometimento_livre_bytes": minima_commit,
               "registros": len(registros), "janelas": diagnostico["janelas_total"],
               "registros_reutilizados_checkpoint": reutilizados,
               "vetores_sha256": hashlib.sha256(dados).hexdigest()}
    destino = raiz / PASTA / ("piloto_memoria" if piloto else "")
    _salvar_imutavel(destino / "vetores.json", dados)
    _salvar_imutavel(destino / "manifesto.json", _json(manifesto))
    # A duração pertence à evidência de execução, não ao produto determinístico.
    if not (destino / "execucao.json").exists():
        _salvar_imutavel(destino / "execucao.json", _json(medicao))
    print(json.dumps(medicao, ensure_ascii=False), flush=True)
    return cache, manifesto


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acao", choices=("baixar", "piloto", "preparar"))
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    raiz = args.raiz.resolve()
    if args.acao == "baixar":
        baixar(raiz)
    else:
        executar(raiz, piloto=args.acao == "piloto")


if __name__ == "__main__":
    main()
