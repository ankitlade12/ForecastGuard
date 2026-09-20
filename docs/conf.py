"""Build the existing Markdown guides and the public Python API."""

from forecastguard import __version__

project = "ForecastGuard"
author = "ForecastGuard contributors"
copyright = "2026, ForecastGuard contributors"
release = __version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.githubpages",
]
exclude_patterns = ["_build", "plans"]
myst_heading_anchors = 6
autodoc_typehints = "description"
autodoc_member_order = "bysource"
html_theme = "furo"
html_title = "ForecastGuard documentation"
html_baseurl = "https://ankitlade12.github.io/ForecastGuard/"
html_theme_options = {
    "source_repository": "https://github.com/ankitlade12/ForecastGuard/",
    "source_branch": "main",
    "source_directory": "docs/",
}
