import unittest

import migration_report


class MigrationReportTestCase(unittest.TestCase):
    def test_report_queries_do_not_reference_legacy_tables(self):
        legacy_tokens = ("words_old", "word_translation_old", "word_set_words_old")
        for sql in migration_report.REPORT_QUERIES.values():
            for token in legacy_tokens:
                self.assertNotIn(token, sql)


if __name__ == "__main__":
    unittest.main()