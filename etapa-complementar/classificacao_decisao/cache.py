"""Extensão explícita do cache somente depois do congelamento do módulo 4.

A classificação lê JSON e calcula sinais numéricos. O encoder é chamado
exclusivamente por ``preparar_reserva`` e recebe apenas os textos faltantes;
nenhum rótulo, tema candidato ou decisão é enviado a ele.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re

from classificacao_experimentos.contexto import (
    assinar, carregar_contexto, conferir_assinaturas, ler_json,
)
from classificacao_experimentos.entradas import (
    carregar_cache, construir_registros, validar_cache,
)
from classificacao_experimentos.motor import validar_modelo
from classificacao_experimentos.preparar import FONTES_PREPARACAO
from classificacao_local.experimento import publicar_produtos
from classificacao_topicos.pipeline import _arquivo_local, _json, _sha, _validar_saida


FONTES_OBRIGATORIAS = {
    "artefatos/melhorias-v1/manifesto.json",
    "artefatos/melhorias-v1/modelo_selecionado.json",
    "artefatos/melhorias-v1/receita_congelada.json",
    "artefatos/melhorias-v1/protocolo.json",
    "artefatos/embeddings-e5-v1/manifesto.json",
    "artefatos/embeddings-e5-v1/vetores.json",
    "artefatos/calibracao-v1/calibrador.json",
    "artefatos/calibracao-v1/politica.json",
    "artefatos/calibracao-v1/metricas_desenvolvimento.json",
    "artefatos/calibracao-v1/predicoes_calibradas.jsonl",
}


def _sha_valido(valor) -> bool:
    return isinstance(valor, str) and re.fullmatch("[0-9a-f]{64}", valor) is not None


def _relativo(raiz: Path, caminho: Path) -> str:
    caminho = Path(caminho)
    if not caminho.is_absolute():
        caminho = raiz / caminho
    # Não aceitar um link no arquivo mesmo quando seu alvo esteja na raiz.
    if caminho.is_symlink() or not caminho.resolve().is_relative_to(raiz):
        raise ValueError("O congelamento deve ser um arquivo local deste repositório.")
    relativo = caminho.resolve().relative_to(raiz).as_posix()
    _arquivo_local(raiz, relativo)
    return relativo


def validar_congelamento(
    raiz: Path, congelamento: Path, congelamento_sha256: str,
) -> dict:
    """Confere o selo externo e todas as fontes antes de abrir a reserva."""
    raiz = raiz.resolve()
    nome = _relativo(raiz, congelamento)
    conteudo = _arquivo_local(raiz, nome).read_bytes()
    if not _sha_valido(congelamento_sha256) or _sha(conteudo) != congelamento_sha256:
        raise ValueError("SHA do congelamento ausente, inválido ou divergente.")
    documento = json.loads(conteudo)
    if not isinstance(documento, dict) or documento.get("schema") != "congelamento_m4_v1":
        raise ValueError("Esquema de congelamento inválido.")
    for campo in ("classificador_congelado", "calibrador_congelado", "politica_congelada"):
        if documento.get(campo) is not True:
            raise ValueError("Classificador, calibrador e política devem estar congelados.")
    grupos = []
    for campo in ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids"):
        valores = documento.get(campo)
        if (not isinstance(valores, list) or not valores
                or any(not isinstance(i, str) or not i.strip() for i in valores)
                or len(set(valores)) != len(valores)):
            raise ValueError("IDs do congelamento ausentes, repetidos ou inválidos.")
        grupos.append(set(valores))
    if any(grupos[i] & grupos[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError("Desenvolvimento, reserva e avaliação devem ser disjuntos.")
    fontes = documento.get("fontes_sha256")
    if (not isinstance(fontes, dict)
            or any(not isinstance(n, str) or not _sha_valido(s)
                   or Path(n).is_absolute() or ".." in Path(n).parts
                   or "\\" in n or Path(n).as_posix() != n
                   for n, s in fontes.items())):
        raise ValueError("Mapa de fontes do congelamento inválido.")
    codigo = {
        p.relative_to(raiz).as_posix()
        for p in (raiz / "classificacao_decisao").glob("*.py")
    }
    configuracoes = {
        p.relative_to(raiz).as_posix()
        for p in (raiz / "config/modulo4").glob("*.json")
    }
    if (not codigo or not configuracoes
            or not (FONTES_OBRIGATORIAS | codigo | configuracoes) <= fontes.keys()
            or nome in fontes):
        raise ValueError("Congelamento omite fontes obrigatórias ou contém referência circular.")
    conferir_assinaturas(raiz, fontes)
    protocolo = ler_json(raiz, "artefatos/melhorias-v1/protocolo.json")
    if any(set(documento[c]) != set(protocolo[c]) for c in (
        "desenvolvimento_ids", "reserva_ids", "avaliacao_ids",
    )):
        raise ValueError("IDs do congelamento divergem do protocolo M3 fixado.")
    return documento


def _contexto(raiz: Path, congelamento: Path, congelamento_sha256: str) -> dict:
    # A ordem é intencional: nenhum contexto com textos reservados antes do selo.
    freeze = validar_congelamento(raiz, congelamento, congelamento_sha256)
    contexto = carregar_contexto(raiz)
    m3 = ler_json(raiz, "artefatos/melhorias-v1/manifesto.json")
    conferir_assinaturas(raiz, m3["entradas_e_implementacao_sha256"])
    conferir_assinaturas(raiz, {
        "artefatos/melhorias-v1/" + nome: sha
        for nome, sha in m3["produtos_sha256"].items()
    })
    config = ler_json(raiz, "config/modulo3/embeddings.json")
    anterior, manifesto_anterior = carregar_cache(
        raiz / "artefatos/embeddings-e5-v1", contexto["registros"], config,
    )
    if manifesto_anterior["fontes_preparacao_sha256"] != assinar(raiz, FONTES_PREPARACAO):
        raise ValueError("Proveniência do cache M3 incompleta ou divergente.")
    protocolo = contexto["protocolo"]
    for campo in ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids"):
        if set(protocolo[campo]) != set(freeze[campo]):
            raise ValueError("Protocolo da preparação diverge do congelamento.")
    existentes = set(protocolo["desenvolvimento_ids"]) | set(protocolo["avaliacao_ids"])
    reserva = set(protocolo["reserva_ids"])
    if set(anterior["questoes"]) != existentes or existentes & reserva:
        raise ValueError("O cache M3 deve cobrir somente desenvolvimento e avaliação.")
    todos = construir_registros(
        contexto["questoes"], contexto["taxonomia"]["registros"], existentes | reserva,
    )
    faltantes = [r for r in todos if r["tipo"] == "questao" and r["id"] in reserva]
    if {r["id"] for r in faltantes} != reserva:
        raise ValueError("Os textos da reserva não cobrem os IDs congelados.")
    fontes = assinar(raiz, sorted(
        set(freeze["fontes_sha256"]) | set(FONTES_PREPARACAO)
        | {_relativo(raiz, congelamento)}
    ))
    if (any(fontes[n] != s for n, s in freeze["fontes_sha256"].items())
            or fontes[_relativo(raiz, congelamento)] != congelamento_sha256):
        raise ValueError("Uma fonte mudou depois da validação do congelamento.")
    return {
        "freeze": freeze, "config": config, "anterior": anterior,
        "registros": todos, "faltantes": faltantes, "fontes": fontes,
        "congelamento_arquivo": _relativo(raiz, congelamento),
        "congelamento_sha256": congelamento_sha256,
    }


def _conferir_extensao(anterior: dict, completo: dict) -> None:
    if (completo.get("schema") != anterior.get("schema")
            or completo.get("dimensoes") != anterior.get("dimensoes")
            or _json(completo.get("temas")) != _json(anterior.get("temas"))
            or not isinstance(completo.get("questoes"), dict)
            or any(_json(completo["questoes"].get(i)) != _json(item)
                   for i, item in anterior["questoes"].items())):
        raise ValueError("A extensão alterou metadados, temas ou vetores existentes do M3.")


def _carregar_com_contexto(diretorio: Path, contexto: dict) -> tuple[dict, dict]:
    if not diretorio.is_dir() or {
        p.name for p in diretorio.iterdir()
    } != {"vetores.json", "manifesto.json"}:
        raise ValueError("Cache completo ausente, parcial ou com arquivos inesperados.")
    cache, manifesto = carregar_cache(
        diretorio, contexto["registros"], contexto["config"],
    )
    _conferir_extensao(contexto["anterior"], cache)
    obrigatorios = {
        "schema": "embeddings_reserva_m4_v1",
        "procedimento": "extensao-e5-small-apos-congelamento-v1",
        "fontes_preparacao_sha256": contexto["fontes"],
        "congelamento_arquivo": contexto["congelamento_arquivo"],
        "congelamento_sha256": contexto["congelamento_sha256"],
        "cache_m3_sha256": contexto["anterior"]["sha256"],
        "questoes_reutilizadas": len(contexto["anterior"]["questoes"]),
        "temas_reutilizados": len(contexto["anterior"]["temas"]),
        "questoes_reserva_preparadas": len(contexto["faltantes"]),
        "rotulos_fornecidos_ao_codificador": False,
        "modelo_escolheu_temas": False,
        "reserva_vetorizada": True,
        "congelamento_validado_antes_da_reserva": True,
        "chamadas_api": 0,
        "custo_api": 0,
    }
    if any(manifesto.get(k) != v for k, v in obrigatorios.items()):
        raise ValueError("Proveniência do cache completo diverge do congelamento.")
    if set(cache["questoes"]) - set(contexto["anterior"]["questoes"]) != {
        r["id"] for r in contexto["faltantes"]
    }:
        raise ValueError("A extensão deve adicionar exatamente as questões da reserva.")
    return cache, manifesto


def carregar_cache_completo(
    raiz: Path, diretorio: Path, congelamento: Path, congelamento_sha256: str,
) -> tuple[dict, dict]:
    """Carrega e valida o cache estendido, sem importar bibliotecas do encoder."""
    raiz = raiz.resolve()
    diretorio = _validar_saida(raiz, diretorio)
    contexto = _contexto(raiz, congelamento, congelamento_sha256)
    resultado = _carregar_com_contexto(diretorio, contexto)
    conferir_assinaturas(raiz, contexto["fontes"])
    return resultado


def _conferir_pesos_e_dependencias(raiz: Path, config: dict) -> tuple[Path, dict]:
    versoes = {n: importlib.metadata.version(n) for n in config["dependencias_preparacao"]}
    if versoes != config["dependencias_preparacao"]:
        raise ValueError("Use as versões fixadas das dependências de preparação M3.")
    pasta = raiz / ".cache-modelos/e5-small"
    for nome, registro in config["arquivos"].items():
        caminho = pasta / nome
        if caminho.is_symlink() or not caminho.is_file():
            raise ValueError("Pesos ausentes; execute baixar-modelo separadamente.")
        with caminho.open("rb") as arquivo:
            sha = hashlib.file_digest(arquivo, "sha256").hexdigest()
        if sha != registro["sha256"] or caminho.stat().st_size != registro["bytes"]:
            raise ValueError("Pesos locais diferentes do modelo M3 fixado.")
    return pasta, versoes


def preparar_reserva(
    raiz: Path, saida: Path, congelamento: Path,
    congelamento_sha256: str, progresso=None,
) -> dict:
    """Reutiliza o M3 e codifica só a reserva, após validar um congelamento."""
    raiz = raiz.resolve()
    saida = _validar_saida(raiz, saida)
    # A preparação nunca sobrescreve um diretório fonte, nem um pai dele.
    for protegido in (
        raiz / "artefatos/embeddings-e5-v1",
        raiz / "artefatos/melhorias-v1",
        raiz / Path(congelamento).parent if not Path(congelamento).is_absolute()
        else Path(congelamento).parent,
    ):
        protegido = protegido.resolve()
        if saida == protegido or saida.is_relative_to(protegido) or protegido.is_relative_to(saida):
            raise ValueError("A extensão deve usar um diretório separado das fontes.")
    contexto = _contexto(raiz, congelamento, congelamento_sha256)
    if saida.exists() and any(saida.iterdir()):
        cache, _ = _carregar_com_contexto(saida, contexto)
        conferir_assinaturas(raiz, contexto["fontes"])
        return {"reutilizado": True, "questoes": len(cache["questoes"]),
                "temas": len(cache["temas"]), "dimensoes": cache["dimensoes"]}
    config = contexto["config"]
    pasta, versoes = _conferir_pesos_e_dependencias(raiz, config)
    # Única entrada que pode carregar ONNX; jamais chamada pelo carregador.
    from classificacao_experimentos.preparacao_embeddings import gerar_cache

    parcial, diagnostico = gerar_cache(
        contexto["faltantes"], config["preparacao"],
        pasta / "modelo.onnx", pasta / "tokenizer.json", progresso=progresso,
    )
    validar_cache(parcial, contexto["faltantes"], config["preparacao"]["dimensoes"])
    cache = deepcopy({k: v for k, v in contexto["anterior"].items() if k != "sha256"})
    cache["questoes"].update(parcial["questoes"])
    _conferir_extensao(contexto["anterior"], cache)
    validar_cache(cache, contexto["registros"], config["preparacao"]["dimensoes"])
    produtos = {"vetores.json": _json(cache)}
    produtos["manifesto.json"] = _json({
        "versao": 1,
        "schema": "embeddings_reserva_m4_v1",
        "procedimento": "extensao-e5-small-apos-congelamento-v1",
        "configuracao": config,
        "fontes_preparacao_sha256": contexto["fontes"],
        "congelamento_arquivo": contexto["congelamento_arquivo"],
        "congelamento_sha256": contexto["congelamento_sha256"],
        "cache_m3_sha256": contexto["anterior"]["sha256"],
        "produtos_sha256": {n: _sha(b) for n, b in produtos.items()},
        "questoes_reutilizadas": len(contexto["anterior"]["questoes"]),
        "temas_reutilizados": len(contexto["anterior"]["temas"]),
        "questoes_reserva_preparadas": len(contexto["faltantes"]),
        "ambiente": {
            "python": platform.python_version(),
            "sistema": platform.system(), "arquitetura": platform.machine(),
            "dependencias": versoes,
        },
        "diagnostico_somente_reserva": diagnostico,
        "rotulos_fornecidos_ao_codificador": False,
        "modelo_escolheu_temas": False,
        "reserva_vetorizada": True,
        "congelamento_validado_antes_da_reserva": True,
        "chamadas_api": 0,
        "custo_api": 0,
    })
    conferir_assinaturas(raiz, contexto["fontes"])
    publicar_produtos(saida, produtos)
    return {
        "reutilizado": False, "questoes": len(cache["questoes"]),
        "temas": len(cache["temas"]), "dimensoes": cache["dimensoes"],
        "questoes_codificadas": len(contexto["faltantes"]),
        "diagnostico_somente_reserva": diagnostico,
    }


def vincular_modelo_estendido(modelo: dict, cache_m3: dict, cache_completo: dict) -> dict:
    """Troca apenas o vínculo do cache; não refaz treino nem altera parâmetros."""
    validar_modelo(modelo)
    for cache in (cache_m3, cache_completo):
        conteudo = {k: v for k, v in cache.items() if k != "sha256"}
        if not _sha_valido(cache.get("sha256")) or cache["sha256"] != _sha(_json(conteudo)):
            raise ValueError("A vinculação exige caches canônicos com SHA conferido.")
    if (modelo["cache_sha256"] != cache_m3["sha256"]
            or modelo["dimensoes"] != cache_m3["dimensoes"]):
        raise ValueError("O modelo não corresponde ao cache M3 original.")
    _conferir_extensao(cache_m3, cache_completo)
    resultado = deepcopy(modelo)
    resultado["cache_sha256"] = cache_completo["sha256"]
    validar_modelo(resultado)
    return resultado
