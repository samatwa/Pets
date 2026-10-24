import csv
import base64
import struct
import io
from datetime import date
from decimal import Decimal
from string import Formatter
import unittest

import chat_report as chat
import dashboard_data as data
import dashboard_i18n as i18n


class LanguageTests(unittest.TestCase):
    def test_translation_placeholders_match(self):
        parser = Formatter()
        for key, texts in i18n.TEXT.items():
            with self.subTest(key=key):
                self.assertEqual(len(texts), 3)
                fields = [{field for _, field, _, _ in parser.parse(text) if field is not None} for text in texts]
                self.assertTrue(all(fields[0] == item for item in fields[1:]))
                self.assertTrue(all(texts))

    def test_flag_labels_are_embedded_images_with_accessible_names(self):
        for language, name in i18n.LANGUAGES.items():
            label = i18n.flag_label(language)
            self.assertTrue(label.startswith(f"![{name}](data:image/png;base64,"))
            encoded = label.split("base64,", 1)[1].split(' "', 1)[0]
            png = base64.b64decode(encoded)
            self.assertEqual(png[:8], bytes([137, 80, 78, 71, 13, 10, 26, 10]))
            width, height = struct.unpack(">II", png[16:24])
            self.assertGreater(width, height)
            self.assertGreaterEqual(height, 30)

    def test_numbers_keep_precision_and_decimal_units(self):
        value = Decimal("9.4410")
        self.assertEqual(i18n.number(value, language="en"), "9.4410")
        self.assertEqual(i18n.number(value, language="nb"), "9,4410")
        self.assertEqual(i18n.number(value, language="ru"), "9,4410")
        self.assertEqual(i18n.number(Decimal("12345.678"), ",.2f", language="en"), "12,345.68")
        self.assertEqual(i18n.number(Decimal("12345.678"), ",.2f", language="nb"), "12 345,68")
        self.assertEqual(i18n.number(Decimal("-0.023"), "+.4f", language="nb"), "-0,0230")

    def test_csv_uses_selected_language_without_changing_dates_or_missing_values(self):
        record = {"Дата": date(2026, 10, 23), **{p: None for p in chat.PAIRS}}
        record["NOK/UAH"] = Decimal("4.8068")
        for language, heading, value in [("en", "Date", "4.8068"), ("nb", "Dato", "4,8068"), ("ru", "Дата", "4,8068")]:
            rows = list(csv.reader(io.StringIO(data.csv_bytes([record], language=language).decode("utf-8-sig")), delimiter=";"))
            self.assertEqual(rows[0], [heading, *chat.PAIRS])
            self.assertEqual(rows[1], ["23.10.2026", "", "", "", "", value])


if __name__ == "__main__":
    unittest.main()

