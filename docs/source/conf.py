from __future__ import annotations

import os
import sys
from pathlib import Path

# Add src/ to sys.path so autodoc can import leasepool when building locally
# without requiring an editable install.
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

if SRC.exists():
    sys.path.insert(0, str(SRC))

project = "leasepool"
author = "Sambhu Nampoothiri G"
copyright = "2026, Sambhu Nampoothiri G"
release = "0.1.1"
version = "0.1.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

html_theme = "furo"
html_title = "leasepool"
html_static_path = ["_static"]

# Autodoc / autosummary
autosummary_generate = True
autodoc_typehints = "description"
autodoc_member_order = "bysource"
autoclass_content = "both"
add_module_names = False

# Napoleon supports Google and NumPy style docstrings.
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True

# External references.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Copybutton: hide Python prompts when users copy code snippets.
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

# Keep nitpicky off initially so Read the Docs does not fail on unresolved
# type aliases while the project is young. Turn this on later once docs mature.
nitpicky = False
