import unittest

from zhenhunxiaoshuo.identity_contract import build_ref_id
from zhenhunxiaoshuo.manipulacao_json.src import json_corrector


class JsonIdentityContractTests(unittest.TestCase):
    def test_normalize_adds_ref_id_and_manifest(self):
        data = {
            "chapters": [{
                "source_url": "https://www.zhenhunxiaoshuo.com/11257.html",
                "chapter_title": "第一百五十二章 魔音",
                "chapter_lead": "【第一百五十二章 魔音】x",
                "paragraphs": ["texto"],
            }]
        }
        result = json_corrector._normalize(data)
        self.assertEqual(result["chapters"][0]["ref_id"], "zhenhun-11257")
        self.assertIn("identity_contract", result)
        self.assertEqual(result["identity_contract"]["total_entries"], 1)


if __name__ == "__main__":
    unittest.main()
