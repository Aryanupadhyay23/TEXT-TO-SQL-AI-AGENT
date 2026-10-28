"""
Root Entrypoint for Streamlit Multipage Frontend.
Run with:
    streamlit run app.py
or:
    streamlit run frontend/app.py
"""

import runpy
from pathlib import Path

app_script = Path(__file__).resolve().parent / "frontend" / "app.py"
runpy.run_path(str(app_script), run_name="__main__")
