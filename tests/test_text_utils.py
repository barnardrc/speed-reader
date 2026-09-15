import unittest

from utils.text_utils import is_header, normalize_text, process_headers


class TextUtilsTests(unittest.TestCase):
    def test_normalize_text_collapses_dash_spacing(self) -> None:
        self.assertEqual(normalize_text("one -- two"), "one— two")

    def test_header_detection_excludes_single_letter_words(self) -> None:
        self.assertTrue(is_header("CHAPTER"))
        self.assertFalse(is_header("I"))
        self.assertFalse(is_header("A"))

    def test_process_headers_groups_heading_and_number(self) -> None:
        self.assertEqual(
            process_headers(["CHAPTER", "12", "Begins", "here"]),
            ["CHAPTER 12", "Begins", "here"],
        )


if __name__ == "__main__":
    unittest.main()
