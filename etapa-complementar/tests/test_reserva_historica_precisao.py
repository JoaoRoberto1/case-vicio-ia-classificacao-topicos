"""Compatibilidade do diagnóstico M8 com o array JSON histórico do M7.

Os vinte registros são sintéticos; nenhum rótulo ou texto real é lido.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from classificacao_precisao.experimento import _comparar_reserva_m7


class ReservaHistoricaPrecisaoTests(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name).resolve()
        self.caminho = self.raiz / "artefatos/catalogo-m7-v1/predicoes_reserva_conhecida.jsonl"
        self.caminho.parent.mkdir(parents=True)
        self.baseline = [
            {"id": f"sintetica_{i:02d}",
             "acertos": {modo: i % 4 in {0, 1} for modo in ("ramo", "imediato", "exato")}}
            for i in range(20)
        ]
        self.predicoes = [
            {"id": f"sintetica_{i:02d}",
             "acertos": {modo: i % 4 in {0, 2} for modo in ("ramo", "imediato", "exato")}}
            for i in range(20)
        ]
        self.conteudo = (json.dumps(self.baseline, indent=2) + "\n").encode("utf-8")
        self.caminho.write_bytes(self.conteudo)

    def test_array_indentado_com_extensao_jsonl_produz_transicoes_pareadas(self):
        antes = deepcopy(self.predicoes)
        resultado = _comparar_reserva_m7(self.raiz, self.predicoes)
        esperado = {"melhorou": 5, "piorou": 5, "ambos_corretos": 5,
                    "ambos_errados": 5, "ganho_liquido": 0}
        self.assertEqual(resultado, {modo: esperado for modo in ("ramo", "imediato", "exato")})
        self.assertEqual(self.predicoes, antes)
        self.assertEqual(self.caminho.read_bytes(), self.conteudo)
        self.assertEqual(hashlib.sha256(self.caminho.read_bytes()).digest(),
                         hashlib.sha256(self.conteudo).digest())

    def test_comparacao_usa_identificadores_em_vez_da_ordem(self):
        esperado = _comparar_reserva_m7(self.raiz, self.predicoes)
        self.assertEqual(_comparar_reserva_m7(self.raiz, list(reversed(self.predicoes))), esperado)

    def test_identificador_incompativel_e_recusado_sem_alterar_arquivo(self):
        alteradas = deepcopy(self.predicoes)
        alteradas[-1]["id"] = "sintetica_ausente"
        with self.assertRaisesRegex(ValueError, "mesmos IDs"):
            _comparar_reserva_m7(self.raiz, alteradas)
        self.assertEqual(self.caminho.read_bytes(), self.conteudo)


if __name__ == "__main__":
    unittest.main()
