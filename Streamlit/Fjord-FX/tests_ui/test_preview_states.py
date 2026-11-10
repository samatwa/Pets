"""Verify that the visual preview exercises the real app without API/DB writes."""
from pathlib import Path
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

import fx_monitor as fx

PREVIEW = Path(__file__).with_name("preview_states.py")


class VisualPreviewTests(unittest.TestCase):
    def tearDown(self):
        st.cache_data.clear()

    def preview(self, scenario):
        app = AppTest.from_file(str(PREVIEW), default_timeout=30)
        app.query_params["scenario"] = scenario
        with patch.object(fx, "fetch", side_effect=AssertionError("Preview must not call an API")), \
                patch.object(fx, "connect", side_effect=AssertionError("Preview must not write a database")):
            app.run()
        self.assertFalse(app.exception)
        return app

    def test_normal_empty_and_error_previews(self):
        for scenario in ("normal", "empty", "offline", "first_error", "storage_error"):
            with self.subTest(scenario=scenario):
                app = self.preview(scenario)
                if scenario == "storage_error":
                    self.assertTrue(app.error)
                    self.assertFalse(app.metric)
                elif scenario in {"empty", "first_error"}:
                    self.assertFalse(app.metric)
                    self.assertFalse(app.toggle)
                    self.assertTrue(app.button(key="refresh"))
                    self.assertEqual(bool(app.warning), scenario == "first_error")
                    if scenario == "first_error":
                        self.assertIn("No saved values are available", app.warning[0].value)
                else:
                    self.assertEqual(app.metric[0].value, "9.4410")
                    self.assertEqual(bool(app.warning), scenario == "offline")

    def test_loading_preview_can_complete_without_network_or_writes(self):
        app = self.preview("loading")
        self.assertEqual(app.metric[0].value, "9.4410")
        self.assertFalse(app.warning)


if __name__ == "__main__":
    unittest.main()
