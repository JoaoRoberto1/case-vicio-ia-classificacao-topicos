import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from classificacao_topicos.diagnostico_cobertura import analisar_cobertura, resumir_cobertura


def linha(identificador, decisao, sinais):
    return {"id": identificador, "decisao": {"estado": "decidido", "decisao": decisao, "sinais": sinais}}


class DiagnosticoCoberturaTests(unittest.TestCase):
    def test_sinais_sobrepostos_nao_duplicam_questoes(self):
        resumo = resumir_cobertura([
            linha("Q0001", "publicar", []),
            linha("Q0002", "revisar", ["revisao_solicitada", "temas_alternativos"]),
            linha("Q0003", "revisar", ["temas_alternativos"]),
            linha("Q0004", "fora", ["fora_confirmado_por_revisao"]),
        ])
        self.assertEqual(resumo["decisoes"], {"publicar": 1, "revisar": 2, "fora": 1})
        self.assertEqual(resumo["cobertura_observada"], 0.25)
        self.assertEqual(resumo["sinais_de_revisao_sobrepostos"], {"revisao_solicitada": 1, "temas_alternativos": 2})
        self.assertEqual(resumo["sinais_exclusivos"], {"temas_alternativos": 1})
        self.assertEqual(sum(c["questoes"] for c in resumo["combinacoes_exclusivas"]), 2)

    def test_correcao_de_fora_continua_identificada_como_revisao(self):
        resumo = resumir_cobertura([linha("Q0001", "revisar", ["fora_rejeitado_por_revisao", "revisao_solicitada"])])
        self.assertEqual(resumo["correcoes_de_fora_para_revisar"], ["Q0001"])
        self.assertEqual(resumo["decisoes"]["publicar"], 0)
        self.assertEqual(resumo["sinais_exclusivos"], {})

    def test_trilha_adulterada_e_reescrita_divergente_sao_rejeitadas(self):
        with tempfile.TemporaryDirectory() as temporaria:
            base = Path(temporaria)
            decisoes = base / "decisoes"
            decisoes.mkdir()
            item = linha("Q0001", "publicar", [])
            item["decisao"]["motivo"] = "Trecho A\u2028Trecho B\u0085Trecho C"
            trilha = (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8")
            manifesto = {"procedimento": "decisoes-v1", "completo": True, "total_questoes": 1,
                         "decisoes": {"publicar": 1, "revisar": 0, "fora": 0},
                         "produtos_sha256": {"trilha_decisoes.jsonl": hashlib.sha256(trilha).hexdigest()}}
            (decisoes / "trilha_decisoes.jsonl").write_bytes(trilha)
            (decisoes / "manifesto_decisoes.json").write_text(json.dumps(manifesto), encoding="utf-8")
            saida = base / "diagnostico.json"
            analisar_cobertura(decisoes, saida)
            antes = (saida.read_bytes(), saida.stat().st_mtime_ns)
            analisar_cobertura(decisoes, saida)
            self.assertEqual(antes, (saida.read_bytes(), saida.stat().st_mtime_ns))
            saida.write_bytes(b"outro resultado\n")
            with self.assertRaisesRegex(ValueError, "existente diverge"):
                analisar_cobertura(decisoes, saida)
            self.assertEqual(saida.read_bytes(), b"outro resultado\n")
            (decisoes / "trilha_decisoes.jsonl").write_bytes(trilha + b"\n")
            with self.assertRaisesRegex(ValueError, "hash congelado"):
                analisar_cobertura(decisoes, base / "novo.json")

    def test_recusa_dupla_contagem_e_saida_dentro_das_decisoes(self):
        item = linha("Q0001", "revisar", ["confianca_abaixo_limiar"])
        with self.assertRaisesRegex(ValueError, "duplicado"):
            resumir_cobertura([item, item])
        with tempfile.TemporaryDirectory() as temporaria:
            base = Path(temporaria)
            with self.assertRaisesRegex(ValueError, "pasta congelada"):
                analisar_cobertura(base, base / "diagnostico.json")
