"""Oura Explorer: a dashboard that shows what moves your sleep.

Run it with: streamlit run app.py
"""

import streamlit as st


def main():
    """Draw the landing page."""
    st.set_page_config(page_title="Oura Explorer", layout="wide")
    st.title("Oura Explorer")
    st.write(
        "Find out what moves your sleep. Upload your Oura export, pick an "
        "outcome you care about, pick a factor to judge it against, and see "
        "how big the effect is and how sure we can be."
    )
    st.info("Under construction: the upload box comes with the next feature.")


if __name__ == "__main__":
    main()
