import unittest

from zhenhunxiaoshuo.producao_epub.src.epub_validator import (
    FINAL_EPUB_DIR,
    VALIDATION_DIR,
    _action_locations,
    validate_final_epub,
)


class EpubValidationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        final_epubs = sorted(FINAL_EPUB_DIR.glob("*.epub"))
        if not final_epubs:
            raise unittest.SkipTest("Nenhum EPUB final disponível para validar.")
        cls.result = validate_final_epub(final_epubs[0])
        cls.report_path = VALIDATION_DIR / "validacao.html"
        cls.html = cls.report_path.read_text(encoding="utf-8")

    def _section(self, start, end):
        begin = self.html.index(start)
        finish = self.html.index(end, begin)
        return self.html[begin:finish]

    def test_integrity_orders_attention_before_ok(self):
        section = self._section("<h2>1. Integridade estrutural</h2>", "<h2>2.")
        self.assertLess(
            section.index('data-status="ATENÇÃO"'),
            section.index('data-status="OK"'),
        )

    def test_covered_items_order_divergence_before_ok(self):
        section = self._section(
            "<h2>2. Itens cobertos pela referência física</h2>",
            "<h2>3.",
        )
        self.assertLess(
            section.index('data-status="DIVERGÊNCIA"'),
            section.index('data-status="OK"'),
        )

    def test_integrity_filter_exists(self):
        section = self._section("<h2>1. Integridade estrutural</h2>", "<h2>2.")
        head = section[section.index("<thead>"):section.index("</thead>")]
        self.assertIn('id="filter-integrity"', head)
        self.assertIn('aria-label="Filtrar por resultado"', head)
        self.assertIn('<option value="Todos">RESULTADO</option>', head)
        self.assertIn('<option value="ATENÇÃO">ATENÇÃO</option>', head)
        self.assertIn('<option value="OK">OK</option>', head)
        self.assertNotIn("<span>Resultado</span>", head)
        self.assertNotIn("<label", head)

    def test_covered_filter_exists(self):
        section = self._section(
            "<h2>2. Itens cobertos pela referência física</h2>",
            "<h2>3.",
        )
        head = section[section.index("<thead>"):section.index("</thead>")]
        self.assertIn('id="filter-covered"', head)
        self.assertIn('aria-label="Filtrar por status"', head)
        self.assertIn('<option value="Todos">STATUS</option>', head)
        self.assertIn('<option value="DIVERGÊNCIA">DIVERGÊNCIA</option>', head)
        self.assertIn('<option value="OK">OK</option>', head)
        self.assertNotIn("<span>Status</span>", head)
        self.assertNotIn("<label", head)

    def test_previous_external_filters_do_not_exist(self):
        self.assertNotIn("Filtro por resultado:", self.html)
        self.assertNotIn("Filtro por status:", self.html)
        self.assertNotIn("table-tools", self.html)

    def test_dynamic_filter_options_omit_missing_states(self):
        integrity = self._section("<h2>1. Integridade estrutural</h2>", "<h2>2.")
        covered = self._section("<h2>2. Itens cobertos pela referência física</h2>", "<h2>3.")
        self.assertNotIn('<option value="ERRO">ERRO</option>', integrity)
        self.assertNotIn('<option value="AVISO">AVISO</option>', covered)

    def test_filter_javascript_is_embedded(self):
        self.assertIn("select[data-filter-target]", self.html)
        self.assertIn("row.hidden", self.html)
        self.assertIn("dataset.status", self.html)

    def test_filters_target_separate_tables(self):
        self.assertIn('data-filter-target="table-integrity"', self.html)
        self.assertIn('data-filter-target="table-covered"', self.html)
        self.assertIn('tbody id="table-integrity"', self.html)
        self.assertIn('tbody id="table-covered"', self.html)

    def test_table_rows_have_data_status(self):
        self.assertIn('data-status="ATENÇÃO"', self.html)
        self.assertIn('data-status="DIVERGÊNCIA"', self.html)
        self.assertIn('data-status="OK"', self.html)

    def test_actionable_divergence_table_columns_exist(self):
        for heading in (
            "Ref ID",
            "Onde ajustar",
            "Como está",
            "Como deveria estar",
            "Motivo",
        ):
            self.assertIn(f"<th>{heading}</th>", self.html)

    def test_action_location_mentions_xhtml_and_h1(self):
        section = self._section("<h2>3. Divergências que exigem ação</h2>", "<h2>4.")
        self.assertIn("XHTML", section)
        self.assertIn("chapter_021.xhtml", section)
        self.assertIn("&lt;h1&gt;", section)

    def test_extra_divergence_has_actionable_comparison(self):
        section = self._section("<h2>3. Divergências que exigem ação</h2>", "<h2>4.")
        self.assertIn("Capítulo 154 [520 Capítulo Extra] Juventude", section)
        self.assertIn("Capítulo Extra de 20 de maio — Juventude", section)
        self.assertIn("título visível o apresenta como capítulo regular", section)

    def test_action_location_mentions_current_navigation_files(self):
        section = self._section("<h2>3. Divergências que exigem ação</h2>", "<h2>4.")
        self.assertIn("NAV", section)
        self.assertIn("não disponível", section)
        self.assertIn("NCX", section)
        self.assertIn("toc.ncx → navPoint", section)
        self.assertNotIn("navPoint de OEBPS/Text/chapter_021.xhtml", section)

    def test_missing_navigation_is_informative_only(self):
        row = {"xhtml": "OPS/Text/custom.xhtml"}
        location = _action_locations(
            row,
            "extra apresentado como capítulo numerado",
            {"nav_path": None, "nav_raw": "", "toc_path": None, "toc_raw": ""},
        )
        self.assertIn("NAV", location)
        self.assertIn("NCX", location)
        self.assertIn("não disponível", location)
        self.assertEqual(1, len(self.result["errors"]))

    def test_action_locations_are_not_hardcoded_to_chapter_021(self):
        row = {"xhtml": "OPS/Text/custom.xhtml"}
        location = _action_locations(
            row,
            "extra apresentado como capítulo numerado",
            {
                "nav_path": "OPS/nav.xhtml",
                "nav_raw": '<a href="Text/custom.xhtml">Título</a>',
                "toc_path": "OPS/toc.ncx",
                "toc_raw": '<content src="Text/custom.xhtml"/>',
            },
        )
        self.assertIn("custom.xhtml", location)
        self.assertIn("toc.ncx", location)
        self.assertIn("toc.ncx → navPoint", location)
        self.assertIn("nav.xhtml", location)
        self.assertIn("nav.xhtml → entrada", location)
        self.assertNotIn("navPoint de OPS/Text/custom.xhtml", location)
        self.assertNotIn("chapter_021.xhtml", location)

    def test_report_is_standalone_html(self):
        self.assertIn("<!doctype html>", self.html)
        self.assertIn("<style>", self.html)
        self.assertIn("<script>", self.html)
        self.assertNotIn("https://", self.html)

    def test_report_is_generated_in_validation_output(self):
        self.assertEqual(self.report_path, self.result["report"])
        self.assertTrue(self.report_path.is_file())


if __name__ == "__main__":
    unittest.main()
