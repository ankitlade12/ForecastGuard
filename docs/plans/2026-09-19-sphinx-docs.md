# Sphinx documentation site

## Scope

Reuse the Markdown guides with MyST, add a Furo landing page and public API
reference with autodoc/Napoleon, and publish to GitHub Pages from `main`.
Keep docs dependencies optional and historical plans outside the built site.

## Implementation and validation

1. Add Sphinx configuration, navigation, API reference and executable examples.
2. Fix repository-relative links that would otherwise break on the site.
3. Build with warnings treated as errors; gate the existing `conclude` check on
   docs as well as tests. Deploy only trusted `main` builds with Pages OIDC.
4. Check rendered navigation, API content, search and mobile layout, then deploy
   and verify the public URL. Update README and package documentation links.
