"""Extração conservadora de texto dos campos originais das questões.

Não corrige OCR, grafia ou conteúdo jurídico. As entidades HTML são decodificadas
uma única vez pelo parser: texto escapado nunca é reinterpretado como marcação.
Quebras de blocos, listas e linhas são preservadas; espaços de apresentação são
reduzidos. A entrada permanece sob responsabilidade de quem chama a função.
"""

from __future__ import annotations

from html.parser import HTMLParser
import re


_BLOCOS = frozenset(
    {
        "address", "article", "aside", "blockquote", "br", "caption", "dd",
        "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main",
        "nav", "ol", "p", "pre", "section", "table", "tbody", "tfoot",
        "thead", "tr", "ul",
    }
)
_DESCARTAR = frozenset(
    {
        "head", "script", "style", "xml", "w:worddocument", "w:latentstyles",
        "o:officedocumentsettings", "o:documentproperties",
    }
)
_VAZIAS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }
)
_CONTROLES = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_QUEBRAS_LITERAIS = re.compile(r"\\r\\n|\\[rnt]")
_ESPACOS_HORIZONTAIS = re.compile(r"[^\S\n]+")


class _ExtratorTexto(HTMLParser):
    """Ignora subárvores de configuração sem fazer uma segunda análise HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.pilha_descartada: list[str] = []
        self.tinha_html = False
        self.avisos: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tinha_html = True
        if self.pilha_descartada or tag in _DESCARTAR:
            if tag not in _VAZIAS:
                self.pilha_descartada.append(tag)
            return
        if tag in _BLOCOS:
            self.partes.append("\n")
        elif tag in {"td", "th"}:
            self.partes.append(" ")
        elif tag == "img":
            alternativo = dict(attrs).get("alt")
            if alternativo and alternativo.strip():
                self.partes.extend((" ", alternativo, " "))
            elif "imagem_sem_texto_alternativo" not in self.avisos:
                self.avisos.append("imagem_sem_texto_alternativo")

    def handle_endtag(self, tag: str) -> None:
        self.tinha_html = True
        if self.pilha_descartada:
            # Aceita fechamento do ancestral mesmo se um filho veio malformado.
            # Não deixa um <br> sem fechamento prender o restante dentro de XML.
            if tag in self.pilha_descartada:
                indice = len(self.pilha_descartada) - 1 - self.pilha_descartada[::-1].index(tag)
                del self.pilha_descartada[indice:]
            return
        if tag in _BLOCOS:
            self.partes.append("\n")
        elif tag in {"td", "th"}:
            self.partes.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VAZIAS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if not self.pilha_descartada:
            self.partes.append(data)

    def handle_comment(self, data: str) -> None:
        # Inclui os enormes comentários condicionais do Word em Q0099.
        self.tinha_html = True

    def handle_decl(self, decl: str) -> None:
        self.tinha_html = True

    def unknown_decl(self, data: str) -> None:
        self.tinha_html = True

    def handle_pi(self, data: str) -> None:
        self.tinha_html = True


def _normalizar_espacos(texto: str) -> str:
    # Não se usa unicode_escape, que corromperia os acentos já decodificados.
    texto = _QUEBRAS_LITERAIS.sub(
        lambda trecho: " " if trecho.group() == r"\t" else "\n", texto
    )
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = _CONTROLES.sub(" ", texto)
    linhas = (_ESPACOS_HORIZONTAIS.sub(" ", linha).strip() for linha in texto.split("\n"))
    return "\n".join(linha for linha in linhas if linha)


def analisar_texto(valor: str) -> dict:
    """Retorna texto, contagens e sinais observáveis de perda ou ausência.

    ``tinha_html`` indica tags, comentários ou declarações reconhecidos pelo
    parser, não a presença isolada de uma entidade como ``&nbsp;``. Os avisos
    não medem correção jurídica e não detectam todo OCR defeituoso. A função
    exige uma string para impedir que campos ausentes virem a palavra "None".
    """
    if not isinstance(valor, str):
        raise TypeError("O texto a normalizar deve ser uma string.")

    parser = _ExtratorTexto()
    parser.feed(valor)
    parser.close()
    extraido = "".join(parser.partes)
    texto = _normalizar_espacos(extraido)
    avisos = list(parser.avisos)
    if parser.pilha_descartada:
        avisos.append("conteudo_html_sem_fechamento")
    if "\ufffd" in extraido:
        avisos.append("caractere_de_substituicao")
    if _CONTROLES.search(extraido):
        avisos.append("caracteres_de_controle")
    if not texto:
        avisos.append("texto_vazio")
    return {
        "texto": texto,
        "tinha_html": parser.tinha_html,
        "caracteres_brutos": len(valor),
        "caracteres_limpos": len(texto),
        "avisos": avisos,
    }


def normalizar_texto(valor: str) -> str:
    """Converte um campo original em texto; use analisar_texto para os avisos."""
    return analisar_texto(valor)["texto"]
