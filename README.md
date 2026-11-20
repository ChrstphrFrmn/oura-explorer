# Oura Explorer

Upload your Oura ring data export and find out what moves your sleep. Pick an outcome you care about (time asleep, deep sleep, HRV and more) and a factor to judge it against (daytime stress, steps, bedtime, a date when something changed). The dashboard shows a chart, the size of the effect in plain units, and how sure it can be.

Final project for ECO 395M (Python, Databases, and Big Data), UT Austin, Fall 2026.

**Status:** in development.

## Run it on your computer

You need Python 3.11 or newer.

```bash
git clone https://github.com/ChrstphrFrmn/oura-explorer.git
cd oura-explorer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the address Streamlit prints (usually http://localhost:8501).

## Run the checks

The same checks run automatically on GitHub for every pull request.

```bash
black --check .
pytest
```
