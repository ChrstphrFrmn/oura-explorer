"""Smoke test: the Streamlit app runs from top to bottom without errors."""

from streamlit.testing.v1 import AppTest


def test_app_runs_and_shows_title():
    """Run app.py the way Streamlit would; check it raised nothing and drew the title."""
    app = AppTest.from_file("../app.py").run()
    assert not app.exception
    assert app.title[0].value == "Oura Explorer"
