"""Preparação e verificação reproduzíveis, usando somente a biblioteca padrão."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from .dados import preparar_dados
from .protocolo import construir_particoes


def _json(objeto: object) -> bytes:
    return (json.dumps(objeto, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _jsonl(registros: list[dict]) -> bytes:
    return b"".join((json.dumps(r, ensure_ascii=False, sort_keys=True,
                               allow_nan=False) + "\n").encode("utf-8")
                    for r in registros)


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _arquivo_local(raiz: Path, relativo: str) -> Path:
    caminho = raiz / relativo
    if (caminho.is_symlink() or not caminho.resolve().is_relative_to(raiz)
            or not caminho.is_file()):
        raise ValueError(f"Arquivo local ausente ou inválido: {relativo}")
    return caminho


def verificar_fontes(raiz: Path) -> dict:
    """Confere as sete fontes contra a versão oficial fixada no repositório."""
    raiz = raiz.resolve()
    arquivo = _arquivo_local(raiz, "config/fontes_oficiais.json")
    referencia = json.loads(arquivo.read_text(encoding="utf-8"))
    esperados = {
        "README-do-case.md", "case-ia-classificacao-de-topicos (2).pdf",
        "anexos/LEIA-ME.md", "anexos/questoes.jsonl", "anexos/temas.csv",
        "anexos/folha_verdade.csv", "anexos/entrega_modelo.csv",
    }
    if set(referencia["arquivos"]) != esperados:
        raise ValueError("O manifesto deve descrever exatamente as sete fontes oficiais.")
    for nome, registro in referencia["arquivos"].items():
        conteudo = _arquivo_local(raiz, nome).read_bytes()
        if _sha(conteudo) != registro["sha256"] or len(conteudo) != registro["bytes"]:
            raise ValueError(f"Fonte diferente da versão oficial fixada: {nome}")
    return referencia


def _assinaturas(raiz: Path) -> dict:
    """Assina o código e a configuração; não inclui relógio ou caminho absoluto."""
    caminhos = sorted([
        *raiz.joinpath("classificacao_topicos").glob("*.py"),
        *raiz.joinpath("config").glob("*.json"),
    ])
    return {p.relative_to(raiz).as_posix():
            _sha(_arquivo_local(raiz, p.relative_to(raiz).as_posix()).read_bytes())
            for p in caminhos}


def construir_produtos(raiz: Path) -> tuple[dict[str, bytes], dict]:
    raiz = raiz.resolve()
    fontes = verificar_fontes(raiz)
    assinaturas = _assinaturas(raiz)
    config = json.loads(_arquivo_local(
        raiz, "config/protocolo_avaliacao.json").read_text(encoding="utf-8"))
    dados = preparar_dados(raiz / "anexos")
    questoes = dados["questoes"]
    rotulos = dados["rotulos"]
    por_id = {q["id"]: q for q in questoes}
    contagens = {
        "questoes": len(questoes),
        "temas": len(dados["taxonomia"]["registros"]),
        "temas_ativos": sum(t["status"] == "active"
                           for t in dados["taxonomia"]["registros"]),
        "rotulos": len(rotulos),
        "avaliacao_oficial": len(questoes) - len(rotulos),
        "rotulos_historicos": sum(por_id[r["id"]]["coorte"] == "historicas"
                                  for r in rotulos),
        "rotulos_recentes": sum(por_id[r["id"]]["coorte"] == "recentes"
                               for r in rotulos),
    }
    if contagens != config["contrato_dados"]:
        raise ValueError(f"Contagens diferentes do contrato versionado: {contagens}")
    particoes = construir_particoes(questoes, rotulos, config)
    diagnostico = {
        "schema_version": 1,
        "contagens": contagens,
        "dados": dados["diagnostico"],
        "escopo": "Preparação estrutural. Nenhuma classificação ou precisão medida.",
    }
    produtos = {
        "questoes_preparadas.jsonl": _jsonl(questoes),
        "temas_preparados.json": _json(dados["taxonomia"]["registros"]),
        "rotulos_referencia.jsonl": _jsonl(rotulos),
        "particoes.json": _json(particoes),
        "diagnostico.json": _json(diagnostico),
    }
    produtos["manifesto.json"] = _json({
        "schema_version": 1,
        "procedimento": "preparacao-etapa2-v1",
        "upstream_commit": fontes["commit"],
        "fontes_sha256": {n: r["sha256"] for n, r in fontes["arquivos"].items()},
        "implementacao_sha256": assinaturas,
        "produtos_sha256": {n: _sha(b) for n, b in produtos.items()},
        "modelo_de_linguagem_utilizado": False,
        "origem_rotulos": "anexos/folha_verdade.csv",
    })
    if fontes != verificar_fontes(raiz) or assinaturas != _assinaturas(raiz):
        raise ValueError("As fontes ou a implementação mudaram durante a preparação.")
    return produtos, contagens


def _validar_saida(raiz: Path, saida: Path) -> Path:
    raiz = raiz.resolve()
    saida = saida if saida.is_absolute() else raiz / saida
    if saida.is_symlink():
        raise ValueError("A saída não pode ser um link simbólico.")
    saida = saida.resolve()
    if saida == raiz or not saida.is_relative_to(raiz):
        raise ValueError("A saída deve ficar em uma subpasta deste repositório.")
    relativo = saida.relative_to(raiz)
    if relativo.parts[0] not in {"artefatos", "tmp"}:
        raise ValueError("Use uma subpasta de artefatos/ ou tmp/ para a saída.")
    if len(relativo.parts) < 2 or (saida.exists() and not saida.is_dir()):
        raise ValueError("A saída deve ser uma subpasta específica, não um arquivo.")
    return saida


def _conferir_existentes(saida: Path, produtos: dict[str, bytes],
                         exigir_completo: bool) -> None:
    if saida.exists():
        inesperados = sorted(p.name for p in saida.iterdir() if p.name not in produtos)
        if inesperados:
            raise ValueError(f"Saída contém arquivos inesperados: {inesperados}")
    for nome, esperado in produtos.items():
        caminho = saida / nome
        if caminho.is_symlink() or (caminho.exists() and not caminho.is_file()):
            raise ValueError(f"Destino de produto inválido: {nome}")
        if caminho.exists() and caminho.read_bytes() != esperado:
            raise ValueError(
                f"Produto divergente: {nome}. Preserve-o e escolha outra --saida.")
        if exigir_completo and not caminho.is_file():
            raise ValueError(f"Produto ausente: {nome}. Execute preparar primeiro.")


def executar_preparacao(raiz: Path, saida: Path) -> dict:
    saida = _validar_saida(raiz, saida)
    produtos, contagens = construir_produtos(raiz)
    _conferir_existentes(saida, produtos, exigir_completo=False)
    saida.mkdir(parents=True, exist_ok=True)
    # O manifesto é publicado por último. Produtos existentes e idênticos são
    # reutilizados; resultados divergentes nunca são substituídos.
    for nome, conteudo in produtos.items():
        destino = saida / nome
        if destino.exists():
            continue
        temporario: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="wb", prefix=".produto-", suffix=".tmp",
                    dir=saida, delete=False) as arquivo:
                temporario = Path(arquivo.name)
                arquivo.write(conteudo)
            if destino.exists():
                if destino.is_symlink() or destino.read_bytes() != conteudo:
                    raise ValueError(f"O destino mudou durante a escrita: {nome}")
            else:
                os.replace(temporario, destino)
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)
    _conferir_existentes(saida, produtos, exigir_completo=True)
    return contagens


def verificar_preparacao(raiz: Path, saida: Path) -> dict:
    saida = _validar_saida(raiz, saida)
    produtos, contagens = construir_produtos(raiz)
    _conferir_existentes(saida, produtos, exigir_completo=True)
    return contagens
