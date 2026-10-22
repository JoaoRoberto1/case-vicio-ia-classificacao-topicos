"""A migração só pode aceitar uma alteração exata de procedência."""
import copy
import unittest

from scripts.migrar_checkpoint_large_m8 import ATUAL, ANTIGO, PROTOCOLO, migrar_indice


class MigracaoCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.atual = {"configuracao_sha256": "config", "entradas_sha256": "textos",
                      "fontes_sha256": {PROTOCOLO: ATUAL, "encoder.py": "codigo"}}
        antigo = copy.deepcopy(self.atual)
        antigo["fontes_sha256"][PROTOCOLO] = ANTIGO
        self.indice = {"schema": "checkpoint_encoder_large_m8_v1", "identidade": antigo,
                       "registros_sha256": {"parcial.json": "vetor"}}

    def test_muda_so_protocolo_sem_mutar_entrada(self):
        original = copy.deepcopy(self.indice)
        saida = migrar_indice(self.indice, self.atual)
        self.assertEqual(saida["identidade"], self.atual)
        self.assertEqual(saida["registros_sha256"], self.indice["registros_sha256"])
        self.assertEqual(self.indice, original)

    def test_recusa_entrada_diferente(self):
        self.indice["identidade"]["entradas_sha256"] = "mudou"
        with self.assertRaises(ValueError):
            migrar_indice(self.indice, self.atual)

    def test_recusa_config_diferente(self):
        self.indice["identidade"]["configuracao_sha256"] = "mudou"
        with self.assertRaises(ValueError):
            migrar_indice(self.indice, self.atual)

    def test_recusa_implementacao_diferente(self):
        self.indice["identidade"]["fontes_sha256"]["encoder.py"] = "mudou"
        with self.assertRaises(ValueError):
            migrar_indice(self.indice, self.atual)

    def test_recusa_outro_protocolo_original(self):
        self.indice["identidade"]["fontes_sha256"][PROTOCOLO] = "outro"
        with self.assertRaises(ValueError):
            migrar_indice(self.indice, self.atual)

    def test_recusa_outro_protocolo_atual(self):
        self.atual["fontes_sha256"][PROTOCOLO] = "outro"
        with self.assertRaises(ValueError):
            migrar_indice(self.indice, self.atual)

    def test_recusa_esquema_desconhecido(self):
        self.indice["schema"] = "outro"
        with self.assertRaises(ValueError):
            migrar_indice(self.indice, self.atual)


if __name__ == "__main__":
    unittest.main()
