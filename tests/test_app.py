"""Smoke test: the Streamlit app runs from top to bottom without errors."""

from streamlit.testing.v1 import AppTest


def test_app_runs_and_shows_the_demo_nights():
    """Run app.py the way Streamlit would; check it drew the title and the night count."""
    app = AppTest.from_file("../app.py").run()
    assert not app.exception
    assert app.title[0].value == "Oura Explorer"
    assert app.success[0].value.startswith("Loaded 269 nights")
