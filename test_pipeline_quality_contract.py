#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from core.atena_pipeline import clean_extracted_text, is_valid_term


class TestPipelineQualityContract(unittest.TestCase):
    def test_clean_extracted_text_removes_script_and_tags(self):
        html = "<html><body><script>const x=1</script><h1>Titulo</h1><p>Conteudo</p></body></html>"
        cleaned = clean_extracted_text(html)
        self.assertIn("Titulo", cleaned)
        self.assertIn("Conteudo", cleaned)
        self.assertNotIn("const x=1", cleaned)
        self.assertNotIn("<h1>", cleaned)

    def test_is_valid_term_filters_noise(self):
        self.assertTrue(is_valid_term("benchmark"))
        self.assertFalse(is_valid_term("ab"))
        self.assertFalse(is_valid_term("https://example.com/path"))
        self.assertFalse(is_valid_term("feature_flag_name_with_noise"))


if __name__ == "__main__":
    unittest.main()
