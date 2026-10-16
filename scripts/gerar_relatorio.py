"""Entrega documental offline; nao importa cliente de API nem le configuracao local.

python -B scripts/gerar_relatorio.py [--saida DIRETORIO] [--pdf] [--verificar]
Texto, previsao e evidencias usam apenas stdlib. PDF usa requirements-relatorio.txt.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from classificacao_topicos.analise_piloto import _consumo, _tentativas


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def json_bytes(valor: dict) -> bytes:
    return (json.dumps(valor, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def cenarios(total: int, publicados: int, config: dict) -> dict:
    campos = ["erros_cenario_minimo", "erros_cenario_central", "erros_cenario_maximo"]
    valores = [config[c] for c in campos]
    if not (0 < publicados <= total) or any(type(v) is not int for v in valores):
        raise ValueError("Denominadores ou cenarios invalidos.")
    minimo, central, maximo = valores
    if not 0 <= minimo <= central <= maximo <= publicados:
        raise ValueError("Cenarios de erros fora de ordem ou do denominador.")
    return {
        "precisao_prevista": (publicados - central) / publicados,
        "precisao_intervalo": [(publicados - maximo) / publicados, (publicados - minimo) / publicados],
        "cobertura_prevista": publicados / total,
        "cobertura_intervalo": [publicados / total, publicados / total],
        "erros_cenario_central": central,
        "erros_cenario_minimo": minimo,
        "erros_cenario_maximo": maximo,
        "natureza": config["natureza"],
    }


def custo_tokens(tokens: dict, precos: dict) -> dict:
    entrada = tokens["promptTokenCount"]
    saida = tokens["candidatesTokenCount"] + tokens["thoughtsTokenCount"]
    cache = tokens.get("cachedContentTokenCount", 0)
    if not 0 <= cache <= entrada:
        raise ValueError("Cache invalido: ja faz parte dos tokens de entrada.")
    return {
        "sem_desconto_cache_usd": (entrada * precos["entrada"] + saida * precos["saida_incluindo_raciocinio"]) / 1_000_000,
        "com_cache_informado_usd": ((entrada - cache) * precos["entrada"] + cache * precos["entrada_cache"] + saida * precos["saida_incluindo_raciocinio"]) / 1_000_000,
    }


def reunir(raiz: Path = RAIZ) -> dict:
    fontes = {}

    def ler(nome: str) -> bytes:
        conteudo = (raiz / nome).read_bytes()
        # Fontes textuais do codigo/docs sao normalizadas como no Git; CSVs e
        # recibos preservam seus bytes. Nao incluir caminhos absolutos/segredos.
        if nome.endswith((".py", ".md", ".txt")):
            conteudo = conteudo.replace(b"\r\n", b"\n")
        fontes[nome] = sha256(conteudo)
        return conteudo

    config = json.loads(ler("config/previsao_v2.json"))
    bruto = ler("publicacao.csv")
    if sha256(bruto) != config["csv_sha256"] or bruto != ler("artefatos/decisoes-v2/publicacao.csv"):
        raise ValueError("CSV diverge da versao congelada da previsao.")
    linhas = list(csv.DictReader(io.StringIO(bruto.decode("utf-8-sig"))))
    ids = [x["id"] for x in linhas]
    if len(ids) != len(set(ids)):
        raise ValueError("ID duplicado no CSV.")
    contagens = {d: sum(x["decisao"] == d for x in linhas) for d in ("publicar", "revisar", "fora")}
    if sum(contagens.values()) != len(linhas):
        raise ValueError("Decisao desconhecida no CSV.")
    por_id = {x["id"]: x for x in linhas}
    if any(por_id[q]["decisao"] != "publicar" for q in config["ressalvas_que_motivam_reserva"]):
        raise ValueError("Ressalvas precisam pertencer ao conjunto previsto.")
    previsao = cenarios(len(linhas), contagens["publicar"], config)
    consumos = {}
    ids_piloto = json.loads(ler("artefatos/piloto/manifesto_piloto.json"))["ids"]
    ids_5c = json.loads(ler("artefatos/experimento-cobertura-v2/ids_selecionados.json"))
    ids_esperados = {"piloto_v1": ids_piloto, "lote_v2_inclui_piloto_v2": ids, "experimento_5c": ids_5c}
    for nome, pasta in (
        ("piloto_v1", "piloto-v1-35-flash-lite"),
        ("lote_v2_inclui_piloto_v2", "lote-v2-35-flash-lite"),
        ("experimento_5c", "desambiguacao-v1-35-flash-lite"),
    ):
        tentativas = []
        arquivos = sorted((raiz / "artefatos/execucoes" / pasta).glob("Q[0-9][0-9][0-9][0-9].json"))
        if {p.stem for p in arquivos} != set(ids_esperados[nome]):
            raise ValueError(f"Conjunto de recibos incompleto ou excedente em {pasta}.")
        for caminho in arquivos:
            recibo = json.loads(ler(caminho.relative_to(raiz).as_posix()))
            if recibo.get("id") != caminho.stem:
                raise ValueError(f"ID interno diverge do nome de recibo: {caminho.name}.")
            tentativas.extend(_tentativas(recibo))
        if not tentativas:
            raise ValueError(f"Recibos ausentes em {pasta}.")
        consumo = _consumo(tentativas)
        consumo["questoes_com_recibo"] = len(arquivos)
        consumo["equivalente_pago_sobre_tokens_conhecidos"] = custo_tokens(consumo["tokens_observados"], config["precos_usd_por_milhao"])
        consumos[nome] = consumo
    # Preserva a origem das evidencias qualitativas; sem recalcular julgamentos.
    diagnostico = json.loads(ler("artefatos/preparacao/diagnostico.json"))
    auditoria = json.loads(ler("artefatos/avaliacao-v1/relatorio_avaliacao.json"))
    experimento = json.loads(ler("artefatos/decisoes-v2/relatorio_experimento.json"))
    for nome in (
        "artefatos/revisao_auditoria-v1/manifesto_revisoes.json",
        "artefatos/experimento-cobertura-v2/manifesto_referencias.json",
        "artefatos/analises/sensibilidade-referencia-v1.json",
        "artefatos/execucoes/lote-v2-35-flash-lite/Q0005.revalidacao.json",
        "docs/modelo_relatorio.md", "scripts/gerar_relatorio.py", "requirements-relatorio.txt",
    ):
        ler(nome)
    h = config["producao_hipoteses"]
    precos = config["precos_usd_por_milhao"]
    custo_reduzido = h["tentativas_por_questao"] * (h["entrada_reduzida_tokens"] * precos["entrada"] + h["saida_reduzida_tokens"] * precos["saida_incluindo_raciocinio"]) / 1_000_000
    revisoes = h["questoes_semana"] * contagens["revisar"] / len(linhas)
    horas = revisoes * h["minutos_por_revisao"] / 60
    return {
        "schema_version": 1, "versao": "entrega-documental-v2", "csv_sha256": sha256(bruto),
        "questoes": len(linhas), "decisoes": contagens, "previsao": previsao,
        "consumo_por_etapa": consumos, "precos": precos,
        "producao": {"hipoteses": h, "revisoes_semana_se_mesma_distribuicao": revisoes,
            "horas_revisao_semana": horas,
            "custo_revisao_por_questao_importada_usd": horas * h["custo_hora_revisor_usd"] / h["questoes_semana"],
            "custo_modelo_reduzido_por_questao_usd": custo_reduzido},
        "diagnostico": diagnostico, "auditoria_historica_v1": {
            "cobertura": auditoria["cobertura"], "comparacao_central": auditoria["comparacao_central"]},
        "experimento_5c": experimento, "fontes_sha256": fontes,
        "limites": [
            "Previsao subjetiva; intervalo de cenarios sem cobertura probabilistica validada.",
            "Consumo ausente, testes sinteticos, possivel chamada interrompida sem recibo e agentes Codex nao entram no custo conhecido.",
            "Precos pagos sao contrafactual; nao representam fatura nem custo zero total do projeto.",
            "Hipoteses de producao nao foram executadas nem validadas neste lote.",
        ],
    }


def texto_previsao(e: dict) -> str:
    p = e["previsao"]
    return (
        f"precisao_prevista: {p['precisao_prevista']:.6f}\n"
        f"precisao_intervalo: {p['precisao_intervalo'][0]:.6f}-{p['precisao_intervalo'][1]:.6f}\n"
        f"cobertura_prevista: {p['cobertura_prevista']:.6f}\n"
        f"cobertura_intervalo: {p['cobertura_intervalo'][0]:.6f}-{p['cobertura_intervalo'][1]:.6f}\n\n"
        "Escopo: versao 2 de publicacao.csv, 77 publicar / 359 questoes. A cobertura\n"
        "e contada, nao estimada para uma populacao futura. Seu intervalo degenerado\n"
        "refere-se exclusivamente a este lote; numeros arredondados a seis casas.\n\n"
        "A previsao de precisao e subjetiva: reserva editorial de quatro possiveis\n"
        "erros entre 77, resultando em 73/77 = 94,8052%. Motivam a cautela as tres\n"
        "referencias com varios centrais aceitos (Q0009, Q0088, Q0187) e o incidente\n"
        "de exposicao a trecho de gabarito de alternativas em Q0179. Nao sao quatro\n"
        "erros observados, nem se presume que os erros estariam nesses quatro IDs.\n"
        "A escolha de quatro e julgamento, nao resultado de calibracao ou modelo\n"
        "estatistico. Nao usamos a media das confiancas autodeclaradas como precisao.\n\n"
        "O intervalo representa cenarios assumidos de zero a oito erros: 69/77 a\n"
        "77/77 = 89,6104% a 100%. Oito duplica a reserva de quatro para explorar\n"
        "mais quatro erros nao detectados; nao ha evidencia de que seja um teto.\n"
        "Nao e intervalo de confianca de 95%, nem faixa empiricamente calibrada.\n"
        "Erros compartilhados entre IAs podem levar o resultado abaixo dela. Sem\n"
        "essas hipoteses de julgamento, os limites identificaveis seriam [0,1].\n\n"
        "Evidencia: o censo historico da v1 encontrou 77 concordancias em 78\n"
        "publicadas frente a referencias provisorias de IA, sem especialista ou\n"
        "rotulos tematicos oficiais. Q0180 foi depois retida em revisao. A retirada\n"
        "e a reutilizacao das referencias nao demonstram precisao de 100% na v2.\n"
        "O censo elimina erro amostral, mas nao erro da referencia. O experimento\n"
        "5C nao aprovou as propostas de ampliacao; nenhuma foi incorporada.\n\n"
        "Para atingir 95% nas 77 publicadas, podem existir no maximo tres erros\n"
        "(74/77 = 96,1039%); quatro resultam em 94,8052%. A meta nao esta comprovada.\n"
        "Mantemos o conjunto congelado sem excluir mais casos para melhorar a\n"
        "aparencia da previsao. Extras, revisar e fora nao tem precisao estimada\n"
        "por este indicador. Consulte relatorio.md e as evidencias reproduziveis\n"
        "em artefatos/entrega-v2/evidencias.json.\n\n"
        f"csv_sha256: {e['csv_sha256']}\n"
    )


def substituir_modelo(modelo: str, valores: dict) -> str:
    def valor(match):
        nome = match.group(1)
        if nome not in valores:
            raise ValueError(f"Campo desconhecido no modelo: {nome}")
        return str(valores[nome])
    return re.sub(r"\{\{(\w+)\}\}", valor, modelo)


def documentos(e: dict, raiz: Path = RAIZ) -> dict[str, bytes]:
    lote = e["consumo_por_etapa"]["lote_v2_inclui_piloto_v2"]
    custo = lote["equivalente_pago_sobre_tokens_conhecidos"]
    def pt(numero, casas=2):
        return f"{numero:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    valores = {
        "cobertura": pt(e["previsao"]["cobertura_prevista"] * 100),
        "precisao": pt(e["previsao"]["precisao_prevista"] * 100),
        "intervalo_inferior": pt(e["previsao"]["precisao_intervalo"][0] * 100),
        "custo_lote_sem_cache": pt(custo["sem_desconto_cache_usd"]),
        "custo_questao_sem_cache": pt(custo["sem_desconto_cache_usd"] / e["questoes"], 4),
        "custo_questao_com_cache": pt(custo["com_cache_informado_usd"] / e["questoes"], 4),
        "custo_50mil_sem_cache": pt(custo["sem_desconto_cache_usd"] / e["questoes"] * 50_000),
        "custo_50mil_com_cache": pt(custo["com_cache_informado_usd"] / e["questoes"] * 50_000),
        "custo_reduzido": pt(e["producao"]["custo_modelo_reduzido_por_questao_usd"], 4),
        "custo_reduzido_semana": pt(e["producao"]["custo_modelo_reduzido_por_questao_usd"] * 50_000),
        "revisoes_semana": pt(e["producao"]["revisoes_semana_se_mesma_distribuicao"], 0),
        "horas_revisao": pt(e["producao"]["horas_revisao_semana"], 0),
        "custo_humano": pt(e["producao"]["custo_revisao_por_questao_importada_usd"], 2),
    }
    modelo = (raiz / "docs/modelo_relatorio.md").read_text(encoding="utf-8")
    return {
        "previsao.txt": texto_previsao(e).encode("utf-8"),
        "relatorio.md": substituir_modelo(modelo, valores).encode("utf-8"),
        "artefatos/entrega-v2/evidencias.json": json_bytes(e),
    }


def pdf(markdown: str) -> bytes:
    import reportlab
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from pypdf import PdfReader

    fonts = Path(reportlab.__file__).parent / "fonts"
    for nome, arquivo in (("Vera", "Vera.ttf"), ("VeraBold", "VeraBd.ttf")):
        pdfmetrics.registerFont(TTFont(nome, str(fonts / arquivo)))
    pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="VeraBold", italic="Vera", boldItalic="VeraBold")
    azul, verde = colors.HexColor("#15344A"), colors.HexColor("#0D756F")
    estilos = {
        "p": ParagraphStyle("p", fontName="Vera", fontSize=9.4, leading=13.3, spaceAfter=7, textColor=azul),
        "h1": ParagraphStyle("h1", fontName="VeraBold", fontSize=22, leading=26, spaceAfter=15, textColor=azul),
        "h2": ParagraphStyle("h2", fontName="VeraBold", fontSize=12, leading=16, spaceBefore=9, spaceAfter=6, textColor=verde),
        "cell": ParagraphStyle("cell", fontName="Vera", fontSize=8.2, leading=11.3, textColor=azul),
        "note": ParagraphStyle("note", fontName="Vera", fontSize=7.6, leading=10.7, textColor=colors.HexColor("#506577")),
    }

    def inline(texto):
        texto = html.escape(texto)
        texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
        texto = re.sub(r"`(.+?)`", r"<b>\1</b>", texto)
        # Links locais ficam legiveis, disponiveis no Markdown; URLs web sao clicaveis.
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<link href="{m[2]}" color="#0D756F">{m[1]}</link>' if m[2].startswith("https://") else m[1], texto)

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#C8D8E0"))
        canvas.line(42, 39, A4[0] - 42, 39)
        canvas.setFont("Vera", 7)
        canvas.setFillColor(azul)
        canvas.drawString(42, 26, "VÍCIO | Case de classificação de tópicos | 16 out 2026")
        canvas.drawRightString(A4[0] - 42, 26, f"{doc.page} / 5")
        canvas.restoreState()

    if markdown.count("<!-- pagina -->") != 4:
        raise ValueError("O relatorio deve conter cinco paginas editoriais.")
    fluxo = []
    for numero, pagina in enumerate(markdown.split("<!-- pagina -->")):
        if numero:
            fluxo.append(PageBreak())
        for bloco in re.split(r"\n\s*\n", pagina.strip()):
            linhas = bloco.splitlines()
            if bloco.startswith("# "):
                fluxo.append(Paragraph(inline(bloco[2:]), estilos["h1"]))
            elif bloco.startswith("## "):
                fluxo.append(Paragraph(inline(bloco[3:]), estilos["h2"]))
            elif bloco.startswith("| "):
                dados = []
                for linha in linhas:
                    if re.fullmatch(r"[| :\-]+", linha):
                        continue
                    dados.append([Paragraph(inline(c.strip()), estilos["cell"]) for c in linha.strip("|").split("|")])
                n = len(dados[0])
                larguras = [116, 395] if n == 2 else ([128, 63, 63, 257] if n == 4 else [511 / n] * n)
                tabela = Table(dados, colWidths=larguras, hAlign=TA_LEFT)
                tabela.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F0F0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#CCDADD")),
                ]))
                fluxo.extend([tabela, Spacer(1, 8)])
            elif bloco.startswith("- "):
                for linha in linhas:
                    fluxo.append(Paragraph("- " + inline(linha.removeprefix("- ")), estilos["p"]))
            else:
                estilo = "note" if bloco.startswith("Fontes:") else "p"
                fluxo.append(Paragraph(inline(" ".join(linhas)), estilos[estilo]))
    stream = io.BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=42, leftMargin=42,
        topMargin=38, bottomMargin=52, title="Case Vício - Classificação de tópicos", author="João Roberto de Oliveira Felix")
    doc.build(fluxo, onFirstPage=rodape, onLaterPages=rodape,
        canvasmaker=lambda *a, **kw: Canvas(*a, **dict(kw, invariant=1)))
    conteudo = stream.getvalue()
    paginas = PdfReader(io.BytesIO(conteudo)).pages
    if len(paginas) != 5:
        inicios = [p.extract_text().splitlines()[2:4] for p in paginas]
        raise ValueError(f"Relatorio com {len(paginas)} paginas, esperado 5. Inicios: {inicios}")
    return conteudo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=RAIZ)
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--verificar", action="store_true", help="Compara sem gravar arquivos.")
    args = parser.parse_args()
    evidencias = reunir()
    produtos = documentos(evidencias)
    if args.pdf:
        produtos["relatorio.pdf"] = pdf(produtos["relatorio.md"].decode("utf-8"))
    for nome, conteudo in produtos.items():
        caminho = args.saida / nome
        if args.verificar:
            if not caminho.exists() or caminho.read_bytes() != conteudo:
                raise ValueError(f"Produto ausente ou divergente: {nome}")
        elif not caminho.exists() or caminho.read_bytes() != conteudo:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_bytes(conteudo)
    print(json.dumps({"produtos": list(produtos), "verificados": args.verificar,
        "csv_sha256": evidencias["csv_sha256"], "chamadas_api": 0}, ensure_ascii=True))


if __name__ == "__main__":
    main()
