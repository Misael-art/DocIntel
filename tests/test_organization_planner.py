import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from organization_planner import decide_record, normalize_filename, validate_execution_manifest


class OrganizationPlannerTests(unittest.TestCase):
    def make_record(self, **overrides):
        record = {
            "file_id": 1,
            "source_path": r"F:\Projects\Alpha\README.md",
            "source_drive": "F:\\",
            "size_bytes": 1024,
            "extensao": ".md",
            "nome_arquivo": "README.md",
            "pasta_raiz": "Projects",
            "fase_correspondente": "FASE_2",
            "status_indexacao": "HASH_CALCULADO",
            "hash_sha256": "",
            "data_modificacao": None,
            "is_c_audit": False,
        }
        record.update(overrides)
        return record

    def test_phase1_small_doc_prefers_google_drive(self):
        record = self.make_record(
            source_path=r"F:\Importante\passaporte.pdf",
            nome_arquivo="passaporte.pdf",
            extensao=".pdf",
            fase_correspondente="FASE_1",
            size_bytes=2048,
        )
        decision = decide_record(record, duplicate_count=0, capacity_by_dest={"I_DRIVE": 10**12, "F_DRIVE": 10**12})
        self.assertEqual(decision["destino_recomendado"], "GOOGLE_DRIVE")
        self.assertEqual(decision["colecao_canonica"], "Pessoal_Critico")

    def test_project_in_f_goes_to_i_drive(self):
        decision = decide_record(self.make_record(), duplicate_count=0, capacity_by_dest={"I_DRIVE": 10**12, "F_DRIVE": 10**12})
        self.assertEqual(decision["destino_recomendado"], "I_DRIVE")
        self.assertEqual(decision["colecao_canonica"], "Projetos_Ativos")

    def test_heavy_rom_stays_on_f_policy(self):
        record = self.make_record(
            source_path=r"F:\ROMs\Chrono Trigger.sfc",
            nome_arquivo="Chrono Trigger.sfc",
            extensao=".sfc",
            fase_correspondente="FASE_4",
            size_bytes=4 * 1024 * 1024,
        )
        decision = decide_record(record, duplicate_count=0, capacity_by_dest={"I_DRIVE": 10**12, "F_DRIVE": 10**12})
        self.assertEqual(decision["destino_recomendado"], "F_DRIVE")
        self.assertEqual(decision["acao_recomendada"], "KEEP_IN_PLACE")

    def test_c_user_project_is_marked_for_drain(self):
        record = self.make_record(
            source_path=r"C:\Users\misae\Desktop\MyApp\package.json",
            source_drive="C:\\",
            nome_arquivo="package.json",
            extensao=".json",
            fase_correspondente="C_USER",
            status_indexacao="C_AUDIT",
            is_c_audit=True,
        )
        decision = decide_record(record, duplicate_count=0, capacity_by_dest={"I_DRIVE": 10**12, "F_DRIVE": 10**12})
        self.assertEqual(decision["acao_recomendada"], "DRAIN_C_BY_COPY")
        self.assertEqual(decision["destino_recomendado"], "I_DRIVE")

    def test_filename_normalization_standardizes_dates(self):
        self.assertEqual(normalize_filename("Relatorio 27-03-2026 FINAL.PDF"), "Relatorio 2026-03-27 FINAL.pdf")

    def test_execution_manifest_validation_blocks_compat_index(self):
        with TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "organization_manifest.csv"
            manifest.write_text("manifest_key,path,rows\nI_DRIVE,foo.csv,12\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                validate_execution_manifest(str(manifest))


if __name__ == "__main__":
    unittest.main()
