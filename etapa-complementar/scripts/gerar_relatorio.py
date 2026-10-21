"""Gera o relatório de quatro páginas; não altera dados ou classificações."""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parent.parent


def gerar(markdown: str) -> bytes:
    import reportlab
    from pypdf import PdfReader
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    fontes = Path(reportlab.__file__).parent / 'fonts'
    for nome, arquivo in [('Vera', 'Vera.ttf'), ('VeraBold', 'VeraBd.ttf')]:
        pdfmetrics.registerFont(TTFont(nome, str(fontes / arquivo)))
    pdfmetrics.registerFontFamily('Vera', normal='Vera', bold='VeraBold', italic='Vera', boldItalic='VeraBold')
    azul = colors.HexColor('#16334B')
    verde = colors.HexColor('#126E68')
    cinza = colors.HexColor('#526775')
    estilos = {
        'p': ParagraphStyle('p', fontName='Vera', fontSize=9.6, leading=13.4, spaceAfter=6.5, textColor=azul),
        'h1': ParagraphStyle('h1', fontName='VeraBold', fontSize=18, leading=23, spaceAfter=10, textColor=azul),
        'h2': ParagraphStyle('h2', fontName='VeraBold', fontSize=11, leading=15, spaceBefore=6, spaceAfter=5, textColor=verde, keepWithNext=True),
        'cell': ParagraphStyle('cell', fontName='Vera', fontSize=8.7, leading=11.8, textColor=azul),
        'note': ParagraphStyle('note', fontName='Vera', fontSize=7.5, leading=10.2, spaceAfter=5, textColor=cinza),
    }
    largura = A4[0] - 80

    def inline(texto):
        texto = html.escape(texto)
        texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto)
        texto = re.sub(r'`(.+?)`', r'<b>\1</b>', texto)
        # O Markdown preserva os caminhos locais; o PDF usa rótulos legíveis.
        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: (
            f'<link href="{m[2]}" color="#126E68">{m[1]}</link>'
            if m[2].startswith('https://') else m[1]), texto)

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(verde)
        canvas.rect(40, A4[1]-23, 25, 3, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor('#CAD9DE'))
        canvas.line(40, 36, A4[0]-40, 36)
        canvas.setFont('Vera', 7)
        canvas.setFillColor(cinza)
        canvas.drawString(40, 24, 'Vício | Etapa complementar | 21 out 2026')
        canvas.drawRightString(A4[0]-40, 24, f'{doc.page} / 4')
        canvas.restoreState()

    paginas = markdown.split('<!-- pagina -->')
    if len(paginas) != 4:
        raise ValueError('São necessárias quatro páginas editoriais, incluindo o memo.')
    if 'João Roberto de Oliveira Felix' not in paginas[0]:
        raise ValueError('Nome completo ausente na primeira página.')
    if not paginas[-1].strip().startswith('# Memo para o professor'):
        raise ValueError('A quarta página deve ser o memo para o professor.')
    fluxo = []
    for numero, pagina in enumerate(paginas):
        if numero:
            fluxo.append(PageBreak())
        for bloco in re.split(r'\n\s*\n', pagina.strip()):
            linhas = bloco.splitlines()
            if bloco.startswith('# '):
                fluxo.append(Paragraph(inline(bloco[2:]), estilos['h1']))
            elif bloco.startswith('## '):
                fluxo.append(Paragraph(inline(bloco[3:]), estilos['h2']))
            elif bloco.startswith('|'):
                dados = []
                for linha in linhas:
                    if re.fullmatch(r'[| :\-]+', linha):
                        continue
                    celulas = linha.strip('|').split('|')
                    dados.append([Paragraph(inline(c.strip()), estilos['cell']) for c in celulas])
                n = len(dados[0])
                if any(len(linha) != n for linha in dados):
                    raise ValueError('Tabela irregular.')
                larguras = ([108, largura-108] if n == 2 else
                            ([largura*0.5, largura*0.23, largura*0.27] if numero==1 else
                             [largura*.27, largura*.30, largura*.43]))
                tabela = Table(dados, colWidths=larguras, hAlign=TA_LEFT, repeatRows=1)
                tabela.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F1F0')),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#CAD9DE')),
                ]))
                fluxo.extend([tabela, Spacer(1, 7)])
            else:
                estilo = 'note' if bloco.startswith('Fontes:') else 'p'
                texto = '<br/>'.join(inline(l.strip()) for l in linhas) if '  \n' in bloco else inline(' '.join(linhas))
                fluxo.append(Paragraph(texto, estilos[estilo]))
    saida = io.BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=A4, leftMargin=40, rightMargin=40,
                           topMargin=38, bottomMargin=48,
                           title='Classificação de tópicos da Vício - Etapa complementar',
                           author='João Roberto de Oliveira Felix')
    doc.build(fluxo, onFirstPage=rodape, onLaterPages=rodape,
              canvasmaker=lambda *a, **kw: Canvas(*a, **dict(kw, invariant=1)))
    resultado = saida.getvalue()
    pdf = PdfReader(io.BytesIO(resultado))
    if len(pdf.pages) != 4:
        raise ValueError(f'O texto ocupou {len(pdf.pages)} páginas; esperado quatro. Reduza o texto ou ajuste o layout.')
    if 'João Roberto de Oliveira Felix' not in pdf.pages[0].extract_text():
        raise ValueError('O nome completo não foi preservado na extração do PDF.')
    if 'Memo para o professor' not in pdf.pages[3].extract_text():
        raise ValueError('Memo não está na quarta página.')
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verificar', action='store_true', help='Regenera em memória e compara, sem escrever.')
    args = parser.parse_args()
    markdown = (RAIZ/'relatorio.md').read_text(encoding='utf-8')
    if '\ufffd' in markdown:
        raise ValueError('Caractere de substituição encontrado no texto.')
    produto = gerar(markdown)
    destino = RAIZ/'relatorio.pdf'
    if destino.is_symlink():
        raise ValueError('Destino não pode ser um link.')
    if args.verificar:
        if not destino.is_file() or destino.read_bytes() != produto:
            raise ValueError('PDF ausente ou divergente.')
    else:
        destino.write_bytes(produto)
    print(json.dumps({'pdf': destino.name, 'paginas': 4, 'bytes': len(produto),
                      'sha256': hashlib.sha256(produto).hexdigest(), 'verificado': args.verificar}))


if __name__ == '__main__':
    main()
