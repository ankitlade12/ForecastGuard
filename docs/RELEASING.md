# Release runbook

This is a maintainer procedure. Completing documentation or local tests does not
publish a release. The current public status is stated in the [README](../README.md).

## Prepare a reviewable release

1. Review the intended source revision, [changelog](../CHANGELOG.md),
   [support matrix](../SUPPORT_MATRIX.md), examples and installation instructions.
2. Run the core checks and optional MLForecast integration in the
   [CI matrix](../.github/workflows/ci.yml). Confirm wheel/sdist metadata checks pass.
3. Install the built wheel in a fresh environment and run both the bundled clean
   example and the intentional failure example from a source checkout. Confirm
   exit codes and JSON/SARIF output, including coverage fields.
4. Confirm the package version in `pyproject.toml` matches `forecastguard.__version__`
   and the intended release tag (`v` plus the version). Curate release notes from
   the unreleased changelog, including scope and compatibility changes.
5. Verify repository visibility, maintainer contact, issue templates, security
   reporting and required branch checks in GitHub. These account settings cannot
   be inferred from committed files.

Merge release changes through the protected `main` branch. An independent
approval, up-to-date passing `conclude` CI, and resolved conversations are
required; see [the branch policy](CI.md#main-branch-protection).

## Publishing setup

The [publish workflow](../.github/workflows/publish.yml) runs when a GitHub release
is published. It uses PyPI trusted publishing with the `pypi` GitHub environment.
Configure the matching PyPI project publisher and repository environment before
triggering it. The workflow verifies the release tag against the package version.

Publishing the GitHub release triggers external publication; do so only after
maintainer release approval. Do not add a PyPI badge or claim an installable
release before the package and its metadata are verified on the registry.

## After publishing

- Test the exact version with a clean `python -m pip install 'forecastguard==VERSION'`.
- Repeat a clean and intentional failure run with the published package.
- Verify the source commit used by consumers of the GitHub Action.
- Update the README install path, release status, changelog and support information.
- Confirm the package metadata links open the user documentation index.

If publication fails, inspect the workflow and fix credentials, publisher mapping
or metadata before retrying. Do not substitute a different artifact for a version
that has already been published.
