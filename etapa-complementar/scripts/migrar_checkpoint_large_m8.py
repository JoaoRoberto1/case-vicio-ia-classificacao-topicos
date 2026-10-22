"""Migração única e auditável da referência de protocolo, sem gerar embeddings.

O protocolo só integra FONTES no preparador congelado. Não é lido por
_registros nem pelo encoder. Configuração, textos, pesos e implementação
permanecem os mesmos; todos os vetores preservados são autenticados antes
de substituir atomicamente a única referência de procedência que mudou.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from classificacao_experimentos.contexto import assinar
from classificacao_experimentos.entradas import validar_cache
from classificacao_experimentos.preparacao_embeddings import _janelas_texto, _validar_registros
from classificacao_precisao.preparar_large import CONFIG, FONTES, _registros, _salvar_checkpoint
from classificacao_topicos.pipeline import _json

PROTOCOLO = "config/modulo8/protocolo.json"
ANTIGO = "dd178b70592028c3c03351a6d6f478d3a91b04dc4a91cdcfde810115ecf88e99"
ATUAL = "4ac9d655cf825b98bfc5b2151466e618637fd7d906deeaf0de6e3cd5730ba115"
INDICE_ORIGINAL = "507d36b0f1ff93a1db64abfaf3f845be508abd7331624208023ee281aa1d6cad"


def sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def identidade_atual(registros, config, fontes):
    return {
        "configuracao_sha256": sha(_json(config)),
        "fontes_sha256": fontes,
        "entradas_sha256": sha(_json([
            {k: r[k] for k in ("tipo", "id", "papel", "texto_sha256")}
            for r in registros
        ])),
    }


def migrar_indice(indice, identidade):
    if indice.get("schema") != "checkpoint_encoder_large_m8_v1":
        raise ValueError("Esquema de checkpoint inesperado.")
    esperado = copy.deepcopy(identidade)
    if esperado["fontes_sha256"].get(PROTOCOLO) != ATUAL:
        raise ValueError("Protocolo atual diverge da migração fixada.")
    esperado["fontes_sha256"][PROTOCOLO] = ANTIGO
    if indice.get("identidade") != esperado:
        raise ValueError("Há divergência além do único hash autorizado.")
    saida = copy.deepcopy(indice)
    saida["identidade"]["fontes_sha256"][PROTOCOLO] = ATUAL
    if saida["identidade"] != identidade:
        raise ValueError("Migração não recompõe a identidade atual.")
    return saida


def preservar(caminho, dados):
    if caminho.exists():
        if caminho.read_bytes() != dados:
            raise ValueError("Evidência anterior diferente; recusado sobrescrever.")
    else:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("xb") as arquivo:
            arquivo.write(dados)


def main():
    from tokenizers import Tokenizer
    pasta = RAIZ / ".cache-modelos/e5-large/checkpoint-completo"
    indice_path = pasta / "indice.json"
    original = indice_path.read_bytes()
    if sha(original) != INDICE_ORIGINAL:
        raise ValueError("O índice não corresponde ao checkpoint da pausa.")
    indice = json.loads(original)
    config = json.loads((RAIZ / CONFIG).read_text(encoding="utf-8"))
    registros = _validar_registros(_registros(RAIZ)[0])
    fontes = assinar(RAIZ, FONTES)
    identidade = identidade_atual(registros, config, fontes)
    atualizado = migrar_indice(indice, identidade)
    mapa = {sha(f"{r['tipo']}:{r['id']}".encode()) + ".json": r for r in registros}
    nomes = set(indice["registros_sha256"])
    if len(nomes) != 594 or not nomes <= mapa.keys():
        raise ValueError("Escopo parcial difere da pausa fixada.")
    presentes = {p.name for p in pasta.iterdir()}
    if presentes != nomes | {"indice.json"}:
        raise ValueError("Arquivo órfão ou temporário encontrado.")
    tokenizer_path = RAIZ / ".cache-modelos/e5-large/tokenizer.json"
    if sha(tokenizer_path.read_bytes()) != config["arquivos"]["tokenizer.json"]["sha256"]:
        raise ValueError("Tokenizer divergente.")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    parametros = config["preparacao"]
    contagens = {"questao": 0, "tema": 0}
    janelas_total = 0
    for nome in sorted(nomes):
        dados = (pasta / nome).read_bytes()
        if sha(dados) != indice["registros_sha256"][nome]:
            raise ValueError("Hash de vetor divergente.")
        registro, item = mapa[nome], json.loads(dados)
        cache = {"schema": "embeddings_e5_v1", "dimensoes": 1024, "questoes": {}, "temas": {}}
        campo = "questoes" if registro["tipo"] == "questao" else "temas"
        cache[campo][registro["id"]] = item
        validar_cache(cache, [registro], 1024)
        janelas, tokens = _janelas_texto(registro["texto"], tokenizer,
                                       parametros["janela_tokens"], parametros["sobreposicao_tokens"])
        if item["tokens"] != tokens or item["janelas"] != len(janelas):
            raise ValueError("Tokenização do checkpoint divergente.")
        for janela in janelas:
            codificacao = tokenizer.encode(f"{registro['papel']}: {janela}", add_special_tokens=True)
            if codificacao.overflowing or not 0 < len(codificacao.ids) <= parametros["max_tokens"]:
                raise ValueError("Janela truncada ou fora do limite.")
        janelas_total += len(janelas)
        contagens[registro["tipo"]] += 1
    novos = _json(atualizado)
    destino = RAIZ / "artefatos/embeddings-e5-large-m8/migracao-protocolo-v1"
    registro = {
        "schema": "migracao_procedencia_checkpoint_large_m8_v1",
        "registrado_em_utc": datetime.now(timezone.utc).isoformat(),
        "indice_antes_sha256": sha(original), "indice_depois_sha256": sha(novos),
        "mudanca_unica": {"campo": "identidade.fontes_sha256." + PROTOCOLO,
                          "antes": ANTIGO, "depois": ATUAL},
        "justificativa": "O protocolo consta somente da lista FONTES no preparador congelado. "
                         "Ele não é lido na construção dos textos, tokenização, inferência ou pooling. "
                         "A alteração documenta a versão do protocolo vigente na retomada; "
                         "os 594 vetores existentes foram gerados quando o índice referenciava o protocolo anterior.",
        "entradas_configuracao_demais_fontes_identicas": True,
        "vetores_preservados_byte_a_byte": True,
        "registros_validados": len(nomes), "contagens": contagens,
        "janelas_validadas": janelas_total, "dimensoes": 1024,
        "validacoes": ["sha256 individual", "texto_sha256", "dimensão", "finitude", "norma L2",
                       "tokens", "janelas", "ausência de truncamento", "ausência de arquivos órfãos"],
        "fontes_sha256": fontes,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "indice_original": "indice_original.json",
        "indice_migrado": "indice_migrado.json",
        "encoder_executado_na_migracao": False,
        "rotulos_ou_predicoes_abertos": False,
    }
    preservar(destino / "indice_original.json", original)
    preservar(destino / "indice_migrado.json", novos)
    preservar(destino / "manifesto.json", _json(registro))
    if indice_path.read_bytes() != original:
        raise ValueError("Índice alterado durante a verificação; migração recusada.")
    _salvar_checkpoint(pasta, "indice.json", novos)
    if indice_path.read_bytes() != novos:
        raise ValueError("Falha ao confirmar o índice migrado.")
    print(json.dumps({"registros_validados": len(nomes), "contagens": contagens,
                      "indice_depois_sha256": sha(novos), "evidencia": str(destino)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
