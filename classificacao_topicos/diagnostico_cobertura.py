"""Contagens dos motivos de revisão, sem alterar política ou decisões."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .execucao import _hash_bytes, _json, _ler


def resumir_cobertura(trilha: list[dict]) -> dict:
    """Conta sinais sobrepostos e combinações exclusivas de questões."""
    if not trilha:
        raise ValueError("A trilha deve conter decisões.")
    vistos, decisoes, sinais, exclusivos, combinacoes = set(), Counter(), Counter(), Counter(), Counter()
    ids_por_sinal: dict[str, list[str]] = {}
    corrigidas = []
    for item in trilha:
        identificador = item.get("id")
        if not isinstance(identificador, str) or not identificador or identificador in vistos:
            raise ValueError("A trilha contém ID ausente ou duplicado.")
        vistos.add(identificador)
        final = item.get("decisao", {})
        decisao = final.get("decisao")
        motivos = final.get("sinais")
        if final.get("estado") != "decidido" or decisao not in {"publicar", "revisar", "fora"}:
            raise ValueError("A trilha deve conter somente decisões finais.")
        if (not isinstance(motivos, list) or any(not isinstance(s, str) or not s for s in motivos)
                or len(set(motivos)) != len(motivos)):
            raise ValueError("Sinais de decisão devem ser textos únicos.")
        if (decisao == "publicar" and motivos) or (decisao == "revisar" and not motivos):
            raise ValueError("Os sinais são incompatíveis com a decisão.")
        decisoes[decisao] += 1
        if decisao != "revisar":
            continue
        sinais.update(motivos)
        combinacoes[tuple(sorted(motivos))] += 1
        for sinal in motivos:
            ids_por_sinal.setdefault(sinal, []).append(identificador)
        if len(motivos) == 1:
            exclusivos[motivos[0]] += 1
        if "fora_rejeitado_por_revisao" in motivos:
            corrigidas.append(identificador)
    total = len(vistos)
    return {
        "schema_version": 1,
        "procedimento": "diagnostico-cobertura-v1",
        "total_questoes": total,
        "decisoes": {d: decisoes[d] for d in ("publicar", "revisar", "fora")},
        "cobertura_observada": decisoes["publicar"] / total,
        "sinais_de_revisao_sobrepostos": dict(sorted(sinais.items())),
        "ids_por_sinal": {s: ids_por_sinal[s] for s in sorted(ids_por_sinal)},
        "sinais_exclusivos": dict(sorted(exclusivos.items())),
        "combinacoes_exclusivas": [
            {"sinais": list(s), "questoes": n}
            for s, n in sorted(combinacoes.items(), key=lambda par: (-par[1], par[0]))
        ],
        "correcoes_de_fora_para_revisar": corrigidas,
        "limites": [
            "Uma questão pode ter vários sinais; suas contagens não devem ser somadas como questões distintas.",
            "As combinações são exclusivas e sua soma é o total de revisar.",
            "Revisão solicitada também pode vir do revisor nas correções de fora; a origem está na trilha.",
            "Sinal exclusivo é apenas diagnóstico operacional: removê-lo não comprova qualidade nem autoriza publicação.",
            "Não estima precisão, não calibra confiança e não altera política, temas ou decisões.",
        ],
    }


def analisar_cobertura(decisoes: Path, saida: Path) -> dict:
    decisoes, saida = Path(decisoes).resolve(), Path(saida).absolute()
    if saida.is_symlink() or saida.resolve().is_relative_to(decisoes):
        raise ValueError("O diagnóstico deve ficar fora da pasta congelada de decisões.")
    manifesto = decisoes / "manifesto_decisoes.json"
    trilha = decisoes / "trilha_decisoes.jsonl"
    m_bytes, t_bytes = _ler(manifesto), _ler(trilha)
    m = _json(m_bytes)
    if (m.get("procedimento") != "decisoes-v1" or m.get("completo") is not True
            or m.get("produtos_sha256", {}).get(trilha.name) != _hash_bytes(t_bytes)):
        raise ValueError("Manifesto incompleto ou trilha divergente do hash congelado.")
    resumo = resumir_cobertura([_json(linha) for linha in t_bytes.decode("utf-8-sig").split("\n") if linha.strip()])
    if m.get("total_questoes") != resumo["total_questoes"] or m.get("decisoes") != resumo["decisoes"]:
        raise ValueError("As contagens da trilha divergem do manifesto.")
    resumo["fontes_sha256"] = {manifesto.name: _hash_bytes(m_bytes), trilha.name: _hash_bytes(t_bytes)}
    conteudo = (json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if _ler(manifesto) != m_bytes or _ler(trilha) != t_bytes:
        raise ValueError("As fontes mudaram durante o diagnóstico.")
    if saida.exists():
        if _ler(saida) != conteudo:
            raise ValueError("O diagnóstico existente diverge; preserve-o e use outro caminho.")
    else:
        saida.parent.mkdir(parents=True, exist_ok=True)
        with saida.open("xb") as arquivo:
            arquivo.write(conteudo)
    return resumo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisoes", type=Path, default=Path("artefatos/decisoes-v1"))
    parser.add_argument("--saida", type=Path, default=Path("artefatos/analises/cobertura-v1.json"))
    args = parser.parse_args()
    try:
        resumo = analisar_cobertura(args.decisoes, args.saida)
    except (ValueError, OSError) as erro:
        parser.exit(2, f"Erro: {erro}\n")
    print(json.dumps({k: resumo[k] for k in ("total_questoes", "decisoes", "cobertura_observada",
                                            "sinais_de_revisao_sobrepostos", "sinais_exclusivos")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
