"""Oura Explorer: a dashboard that shows what moves your sleep.

Run it with: streamlit run app.py
"""

from pathlib import Path

import streamlit as st

from oura_explorer.load import load_export, night_summary

DEMO_EXPORT = Path(__file__).parent / "demo-data"


@st.cache_resource
def demo_database():
    """Load the demo export once and keep its database for every visit."""
    return load_export(DEMO_EXPORT)


def main():
    """Draw the landing page."""
    st.set_page_config(page_title="Oura Explorer", layout="wide")
    st.title("Oura Explorer")
    st.write(
        "Find out what moves your sleep. Upload your Oura export, pick an "
        "outcome you care about, pick a factor to judge it against, and see "
        "how big the effect is and how sure we can be."
    )
    count, first, last = night_summary(demo_database())
    st.success(
        f"Loaded {count} nights from the demo export, "
        f"{first:%b} {first.day} to {last:%b} {last.day}, {last.year}."
    )
    st.info("Under construction: uploading your own export comes later.")


if __name__ == "__main__":
    main()
