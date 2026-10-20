"""Formato de entrega e autoavaliação, com denominadores explícitos."""

from collections import Counter
import csv
import io
import math


COLUNAS = ["id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"]


def gerar_csv(registros: list[dict]) -> bytes:
    if len({r["id"] for r in registros}) != len(registros):
        raise ValueError("IDs repetidos na entrega.")
    arquivo = io.StringIO(newline="")
    escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, lineterminator="\n")
    escritor.writeheader()
    for registro in sorted(registros, key=lambda r: r["id"]):
        linha = {c: registro[c] for c in COLUNAS}
        p = linha["confianca"]
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("Confiança inválida na entrega.")
        linha["confianca"] = f"{p:.8f}"
        escritor.writerow(linha)
    return arquivo.getvalue().encode("utf-8")


def validar_csv(conteudo: bytes, ids: set[str], taxonomia: dict) -> dict:
    leitor = csv.DictReader(io.StringIO(conteudo.decode("utf-8"), newline=""))
    if leitor.fieldnames != COLUNAS:
        raise ValueError("Cabeçalho diferente do contrato oficial.")
    linhas = list(leitor)
    if len(linhas) != len(ids) or {r["id"] for r in linhas} != ids:
        raise ValueError("A entrega deve conter uma linha por questão.")
    por_id = taxonomia["por_id"]
    for r in linhas:
        if None in r or any(r[c] is None for c in COLUNAS):
            raise ValueError("Colunas incompletas na entrega.")
        if r["decisao"] not in {"publicar", "revisar", "fora"}:
            raise ValueError("Decisão inválida.")
        if r["decisao"] in {"revisar", "fora"} and not r["motivo"].strip():
            raise ValueError("Revisão e fora exigem motivo.")
        tema = r["tema_central_id"]
        if r["decisao"] == "fora":
            if tema or r["extras_ids"]:
                raise ValueError("Fora deve ter tema e extras vazios.")
        elif tema not in por_id or por_id[tema]["status"] != "active" or int(por_id[tema]["nivel"]) < 1:
            raise ValueError("Tema central ausente, inativo ou disciplina.")
        if r["extras_ids"]:
            raise ValueError("Este procedimento congelado não prevê extras.")
        try:
            p = float(r["confianca"])
        except ValueError:
            raise ValueError("Confiança não numérica.") from None
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("Confiança fora do intervalo [0,1].")
    return {"linhas": len(linhas), "decisoes": dict(sorted(Counter(r["decisao"] for r in linhas).items()))}


def gerar_previsao(
    registros: list[dict], avaliacao_ids: set[str], metricas_reserva: dict,
    referencias_excluidas: int,
) -> tuple[dict, bytes]:
    if len({r["id"] for r in registros}) != len(registros):
        raise ValueError("IDs repetidos na previsão.")
    if (type(referencias_excluidas) is not int or referencias_excluidas < 0
            or any(r["decisao"] not in {"publicar", "revisar", "fora"} for r in registros)):
        raise ValueError("Contagem de referências ou decisão inválida.")
    avaliacao = [r for r in registros if r["id"] in avaliacao_ids]
    if not avaliacao_ids or {r["id"] for r in avaliacao} != avaliacao_ids:
        raise ValueError("Questões da avaliação ausentes.")
    if len(registros) - len(avaliacao) != referencias_excluidas:
        raise ValueError("Denominador de referências excluídas divergente.")
    publicadas = [r for r in avaliacao if r["decisao"] == "publicar"]
    for r in publicadas:
        p = r["confianca"]
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("Probabilidade inválida para a previsão.")
    n, total = len(publicadas), len(avaliacao)
    cobertura = n / total
    precisao = math.fsum(r["confianca"] for r in publicadas) / n if n else None
    referencia = metricas_reserva["geral"]["publicacao"]
    nr, kr = referencia["n"], referencia["acertos"]
    if type(nr) is not int or type(kr) is not int or not 0 <= kr <= nr:
        raise ValueError("Contagens de publicação na reserva inválidas.")
    ir = referencia["intervalo_wilson_95"]
    if nr:
        if (not isinstance(ir, dict) or set(ir) != {"inferior", "superior"}
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) for v in ir.values())
                or not 0 <= ir["inferior"] <= ir["superior"] <= 1):
            raise ValueError("Intervalo da reserva inválido.")
    elif ir is not None:
        raise ValueError("Reserva sem publicações não possui intervalo estimado.")
    if n and referencia["n"]:
        intervalo = referencia["intervalo_wilson_95"]
        natureza = "Wilson 95% das publicadas na reserva, transportado sob hipótese de comparabilidade."
        nivel = 0.95
    else:
        intervalo = {"inferior": 0.0, "superior": 1.0}
        natureza = "Domínio sem informação; não é um intervalo de confiança estimado."
        nivel = None
    previsao = {
        "schema": "previsao_m4_v1", "avaliacao_total": total,
        "referencias_excluidas": referencias_excluidas, "publicadas": n,
        "precisao_prevista": precisao,
        "precisao_metodo": "Média das probabilidades calibradas nas publicadas; indefinida se não há publicadas.",
        "precisao_intervalo": intervalo, "precisao_intervalo_natureza": natureza,
        "precisao_intervalo_nivel": nivel,
        "precisao_txt_sentinela_zero": n == 0,
        "cobertura_prevista": cobertura,
        "cobertura_intervalo": {"inferior": cobertura, "superior": cobertura},
        "cobertura_metodo": "Contagem conhecida; não é estimativa amostral.",
        "referencia_reserva": referencia,
        "ajuste_final_testado_independentemente": False,
        "meta_95_comprovada": False,
        "decisoes_avaliacao": {d: sum(r["decisao"] == d for r in avaliacao)
                              for d in ("publicar", "revisar", "fora")},
    }
    texto = [
        f"precisao_prevista: {precisao if precisao is not None else 0.0:.8f}",
        f"precisao_intervalo: {intervalo['inferior']:.8f}-{intervalo['superior']:.8f}",
        f"cobertura_prevista: {cobertura:.8f}",
        f"cobertura_intervalo: {cobertura:.8f}-{cobertura:.8f}",
        "",
        f"A previsão considera apenas as {total} questões fora da folha-verdade; "
        f"as {referencias_excluidas} referências humanas foram excluídas dos denominadores.",
        f"Foram publicadas {n} de {total} questões. A cobertura é uma contagem exata.",
        "",
    ]
    if not n:
        texto.extend([
            "Não há questões publicadas. Portanto, a precisão entre publicadas é "
            "matematicamente indefinida (denominador zero). O valor 0.00000000 na primeira "
            "linha é apenas uma sentinela para manter o formato numérico exigido; não "
            "significa previsão de 0% de acerto. O JSON de evidências registra null.",
            "O intervalo 0.00000000-1.00000000 representa ausência de informação sobre "
            "precisão entre publicadas; não é um intervalo de confiança calculado. "
            "Cobertura zero não demonstra o atendimento da meta de precisão.",
        ])
    else:
        texto.extend([
            "A precisão prevista é a média das probabilidades de acerto por ramo, "
            "calibradas com referências humanas de desenvolvimento. O escore de recuperação "
            "não foi usado diretamente como probabilidade.",
            f"A reserva final teve {referencia['acertos']} acertos em "
            f"{referencia['n']} publicações. {natureza}",
            "Quando há suporte na reserva, o intervalo descreve a precisão do procedimento "
            "avaliado nessa amostra; sua aplicação às novas questões pressupõe comparabilidade. "
            "Ele não é um intervalo calculado para a média das probabilidades das questões finais.",
        ])
    texto.extend([
        "",
        "As 80 referências de desenvolvimento orientaram a escolha do classificador, a "
        "calibração e a política. As 20 reservadas foram avaliadas após o congelamento; "
        "seus resultados não alteraram os componentes ou os limiares.",
        "O classificador final foi reajustado com os textos das 100 referências, mantendo "
        "a receita e o calibrador ajustado nas 80 predições fora da amostra. Esse reajuste "
        "altera o IDF lexical e não recebeu outro teste independente. Os rótulos dos "
        "vizinhos não contribuem para o escore da receita selecionada.",
        "As referências humanas são do banco anterior. As 300 questões recentes não têm "
        "rótulos disponíveis; mudanças de distribuição e efeitos do reajuste não são "
        "quantificados pelo intervalo. A meta de 95% não é declarada comprovada.",
        "Questões incertas são encaminhadas à revisão. A decisão fora não foi automatizada "
        "com o suporte disponível; baixa confiança não demonstra ausência de tema adequado.",
        "",
    ])
    return previsao, "\n".join(texto).encode("utf-8")
