"""Registra intervalos observados de questões novas, sem executar o encoder.

Os timestamps são metadados do sistema de arquivos, não um benchmark isolado.
O primeiro registro apenas delimita o início: sua própria geração não entra
no intervalo medido. Só os 64 registros seguintes compõem o denominador.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from classificacao_precisao.preparar_large import _registros
from classificacao_topicos.pipeline import _json


def medir_intervalos(registros):
    if len(registros) < 2:
        raise ValueError("São necessários pelo menos dois registros.")
    tempos = [r["concluido_mtime_ns"] for r in registros]
    if any(type(t) is not int or t <= 0 for t in tempos):
        raise ValueError("Timestamp inválido.")
    if any(a >= b for a, b in zip(tempos, tempos[1:])):
        raise ValueError("Timestamps não são estritamente crescentes.")
    intervalos = [b - a for a, b in zip(tempos, tempos[1:])]
    return {"registros_medidos": len(registros) - 1,
            "intervalos_ns": intervalos,
            "segundos": (tempos[-1] - tempos[0]) / 1_000_000_000,
            "janelas_medidas": sum(r["janelas"] for r in registros[1:]),
            "tokens_corpo_medidos": sum(r["tokens"] for r in registros[1:])}


def main():
    base = RAIZ / "artefatos/embeddings-e5-large-m8"
    pasta = RAIZ / ".cache-modelos/e5-large/checkpoint-completo"
    original = json.loads((base / "migracao-protocolo-v1/indice_original.json").read_text(encoding="utf-8"))
    atual = json.loads((pasta / "indice.json").read_text(encoding="utf-8"))
    inicio = json.loads((base / "retomada-v1/inicio.json").read_text(encoding="utf-8"))
    inicio_ns = int(datetime.fromisoformat(inicio["inicio_utc"]).timestamp() * 1_000_000_000)
    registros = []
    for r in _registros(RAIZ)[0]:
        if r["tipo"] != "questao":
            continue
        nome = hashlib.sha256(f"questao:{r['id']}".encode()).hexdigest() + ".json"
        if nome in original["registros_sha256"]:
            continue
        if nome not in atual["registros_sha256"]:
            raise ValueError("As 65 questões novas ainda não terminaram.")
        caminho = pasta / nome
        antes = caminho.stat().st_mtime_ns
        dados = caminho.read_bytes()
        assinatura = hashlib.sha256(dados).hexdigest()
        item = json.loads(dados)
        if (assinatura != atual["registros_sha256"][nome]
                or item["texto_sha256"] != r["texto_sha256"]
                or caminho.stat().st_mtime_ns != antes or antes <= inicio_ns):
            raise ValueError("Procedência ou timestamp de registro divergente.")
        registros.append({"id": r["id"], "arquivo": nome, "sha256": assinatura,
                          "texto_sha256": item["texto_sha256"], "tokens": item["tokens"],
                          "janelas": item["janelas"], "concluido_mtime_ns": antes,
                          "concluido_utc": datetime.fromtimestamp(antes / 1e9, timezone.utc).isoformat()})
    if len(registros) != 65:
        raise ValueError("Escopo diferente das 65 questões da retomada.")
    medicao = medir_intervalos(registros)
    produto = {
        "schema": "intervalos_questoes_encoder_large_m8_v1",
        "registrado_em_utc": datetime.now(timezone.utc).isoformat(),
        "metodo": "Diferença entre st_mtime_ns dos arquivos de conclusão consecutivos. "
                  "Do fim da primeira questão nova ao fim da última: 64 gerações de questões, "
                  "incluindo gravação, atualização de índice e demais trabalho entre as conclusões.",
        "registros_retomados_antes_do_bloco": 594,
        "registros_observados": 65,
        **medicao,
        "primeiro_registro_excluido_do_denominador": registros[0]["id"],
        "carga_encoder_ou_594_reutilizados_incluidos": False,
        "temas_incluidos": False,
        "limites": ["Bloco contíguo não aleatório de 64 questões, com comprimentos próprios.",
                    "Host compartilhado, sem isolamento de carga de CPU, RAM ou disco.",
                    "Metadados de tempo do sistema de arquivos; não são um relógio monotônico instrumentado.",
                    "Não mede o tempo total da geração desde zero nem custo integral da aplicação.",
                    "Este registro não afirma representatividade da carga de 50 mil questões."],
        "registros": registros,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    destino = base / "retomada-v1/tempo_questoes.json"
    with destino.open("xb") as arquivo:
        arquivo.write(_json(produto))
    print(json.dumps({k: produto[k] for k in ("registros_observados", "registros_medidos", "segundos", "janelas_medidas")}))


if __name__ == "__main__":
    main()
