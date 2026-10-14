"""Regressões de perda de conteúdo e da contaminação HTML observada no lote."""

import json
from pathlib import Path
import unittest

from classificacao_topicos.texto import analisar_texto, normalizar_texto


class NormalizacaoTextoTest(unittest.TestCase):
    def test_preserva_unicode_comparacao_e_texto_sem_html(self):
        texto = "A < B e B > C; ação, § 1º, R$ 1.000,00, 10.826/2003."
        analise = analisar_texto(texto)
        self.assertEqual(analise["texto"], texto)
        self.assertFalse(analise["tinha_html"])
        self.assertEqual(analise["avisos"], [])

    def test_separa_blocos_listas_celulas_e_br_sem_colar_palavras(self):
        html = (
            "<p>Primeiro <b>item</b>.</p><div>Segundo<br>Terceiro</div>"
            "<ul><li>Um</li><li>Dois</li></ul>"
            "<table><tr><td>Nome</td><td>Valor</td></tr></table>"
        )
        self.assertEqual(
            normalizar_texto(html),
            "Primeiro item.\nSegundo\nTerceiro\nUm\nDois\nNome Valor",
        )

    def test_normaliza_nbsp_quebras_reais_e_literais_sem_recodificar_unicode(self):
        texto = "  A\u00a0 B\r\nC\rD\tE  " + r"\r\nF\nG\tH\u00e7" + "\n\nI"
        self.assertEqual(normalizar_texto(texto), "A B\nC\nD E\nF\nG H\\u00e7\nI")

    def test_decodifica_entidades_uma_vez_sem_transformar_texto_em_tag(self):
        html = "<p>&lt;script&gt;conteúdo&lt;/script&gt; &amp;lt;b&amp;gt; &amp; ação</p>"
        self.assertEqual(
            normalizar_texto(html), "<script>conteúdo</script> &lt;b&gt; & ação"
        )

    def test_remove_script_style_xml_e_comentarios_condicionais_word(self):
        html = (
            "<head><title>Configuração</title></head><p>Antes</p>"
            "<!--[if gte mso 9]><xml>SEGREDO WORD</xml><![endif]-->"
            "<style>.MsoNormal { color:red; }</style><script>alert('x')</script>"
            "<xml><w:WordDocument><w:View>Normal</w:View><br></w:WordDocument></xml>"
            "<o:OfficeDocumentSettings>Configuração</o:OfficeDocumentSettings>"
            "<w:LatentStyles><w:LsdException/></w:LatentStyles><p>Depois</p>"
        )
        analise = analisar_texto(html)
        self.assertEqual(analise["texto"], "Antes\nDepois")
        self.assertTrue(analise["tinha_html"])
        self.assertEqual(analise["avisos"], [])

    def test_html_malformado_preserva_conteudo_visivel(self):
        self.assertEqual(normalizar_texto("<p>Primeiro<p>Segundo<br/>Fim"), "Primeiro\nSegundo\nFim")
        self.assertEqual(normalizar_texto("<b>Texto <i>sem fechamento"), "Texto sem fechamento")
        self.assertEqual(normalizar_texto("Texto com < incompleto"), "Texto com < incompleto")

    def test_xml_malformado_nao_descarta_texto_depois_do_fechamento(self):
        html = "<xml><w:WordDocument>Configuração</xml><p>Conteúdo</p>"
        self.assertEqual(normalizar_texto(html), "Conteúdo")

    def test_registra_bloco_descartado_sem_fechamento(self):
        analise = analisar_texto("<p>Antes</p><style>CSS não fechado")
        self.assertEqual(analise["texto"], "Antes")
        self.assertIn("conteudo_html_sem_fechamento", analise["avisos"])

    def test_texto_apenas_br_e_texto_vazio_nao_geram_falso_conteudo(self):
        for entrada in ("", "   ", "<br>", "<p>&nbsp;</p>", "<!-- só comentário -->"):
            with self.subTest(entrada=entrada):
                analise = analisar_texto(entrada)
                self.assertEqual(analise["texto"], "")
                self.assertEqual(analise["caracteres_limpos"], 0)
                self.assertIn("texto_vazio", analise["avisos"])
        self.assertTrue(analisar_texto("<br>")["tinha_html"])

    def test_imagem_preserva_alt_e_sinaliza_quando_nao_tem_texto(self):
        analise = analisar_texto('<p>Ver<img alt="A &amp; B" src="x">agora<img src="y"></p>')
        self.assertEqual(analise["texto"], "Ver A & B agora")
        self.assertEqual(analise["avisos"], ["imagem_sem_texto_alternativo"])

    def test_sinaliza_controles_e_substituicao_sem_inventar_correcao_ocr(self):
        analise = analisar_texto("pol�cia\x00c�rro fi itercepiado")
        self.assertEqual(analise["texto"], "pol�cia c�rro fi itercepiado")
        self.assertEqual(analise["avisos"], ["caractere_de_substituicao", "caracteres_de_controle"])

    def test_contagens_referem_se_a_caracteres_nao_bytes(self):
        analise = analisar_texto("<p>ação</p>")
        self.assertEqual(analise["caracteres_brutos"], 11)
        self.assertEqual(analise["caracteres_limpos"], 4)

    def test_rejeita_campo_ausente_sem_converter_none_em_texto(self):
        with self.assertRaisesRegex(TypeError, "string"):
            normalizar_texto(None)


class RegressoesLoteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fonte = Path(__file__).resolve().parents[1] / "questoes.jsonl"
        cls.questoes = {
            linha["id"]: linha
            for linha in map(json.loads, fonte.read_text(encoding="utf-8-sig").splitlines())
        }

    def test_q0099_preserva_todas_as_alternativas_sem_configuracao_word(self):
        esperado = {
            "A": "Filomena praticou o delito de resistência, ao passo que os fiscais cometeram o delito de lesão corporal leve;",
            "B": "Filomena praticou o delito de resistência, na modalidade tentada, ao passo que os fiscais não cometeram crime algum, pois agiram amparados em excludente de ilicitude;",
            "C": "Filomena praticou o delito de resistência qualificada, ao passo que os fiscais não cometeram crime algum, pois agiram amparados em excludente de ilicitude;",
            "D": "Filomena praticou os delitos de resistência e lesões corporais leves, ao passo que os fiscais não cometeram crime algum, pois agiram amparados em excludente de ilicitude;",
            "E": "Filomena praticou os delitos de resistências, na modalidade tentada, e lesões corporais leves, ao passo que os fiscais cometeram os crimes de lesão corporal leve e abuso de autoridade.",
        }
        for letra, original in self.questoes["Q0099"]["alternativas"].items():
            with self.subTest(alternativa=letra):
                analise = analisar_texto(original)
                self.assertEqual(" ".join(analise["texto"].split()), esperado[letra])
                self.assertNotIn("mso-", analise["texto"])
                self.assertNotIn("WordDocument", analise["texto"])
                self.assertEqual(analise["avisos"], [])
                if letra in "BCD":
                    self.assertGreater(analise["caracteres_brutos"], 35_000)
                    self.assertLess(analise["caracteres_limpos"], 200)

    def test_q0107_comando_substantivo_permanece_inteiro(self):
        comando = self.questoes["Q0107"]["comando"]
        self.assertEqual(normalizar_texto(comando), comando)
        self.assertIn("crime de falsa identidade", normalizar_texto(comando))

    def test_q0003_normaliza_quebra_literal_preservando_ministerio_publico(self):
        original = self.questoes["Q0003"]["alternativas"]["A"]
        self.assertIn(r"\n", original)
        texto = normalizar_texto(original)
        self.assertNotIn(r"\n", texto)
        self.assertIn("Ministério Público", " ".join(texto.split()))


if __name__ == "__main__":
    unittest.main()
