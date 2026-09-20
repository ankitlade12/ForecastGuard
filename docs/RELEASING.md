# Release runbook

This is a maintainer procedure. Completing documentation or local tests does not
publish a release. The current public status is stated in the [README](https://github.com/ankitlade12/ForecastGuard/blob/main/README.md).

## Prepare a reviewable release

1. Review the intended source revision, [changelog](https://github.com/ankitlade12/ForecastGuard/blob/main/CHANGELOG.md),
   [support matrix](https://github.com/ankitlade12/ForecastGuard/blob/main/SUPPORT_MATRIX.md), examples and installation instructions.
2. Run the core checks and optional MLForecast integration in the
   [CI matrix](https://github.com/ankitlade12/ForecastGuard/blob/main/.github/workflows/ci.yml). Confirm wheel/sdist metadata checks pass.
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
required for non-admin contributors. Repository administrators can bypass these
requirements; see [the branch policy](CI.md#main-branch-protection).

## Publishing setup

The [publish workflow](https://github.com/ankitlade12/ForecastGuard/blob/main/.github/workflows/publish.yml) runs when a GitHub release
is published. It uses PyPI trusted publishing with the `pypi` GitHub environment.
Configure the matching PyPI project publisher and repository environment before
triggering it. The workflow verifies the release tag against the package version.

For the first release, sign into the intended owner account and add a
[pending publisher](https://pypi.org/manage/account/publishing/) on PyPI:

| Field | Value |
|---|---|
| PyPI project name | `forecastguard` |
| GitHub owner | `ankitlade12` |
| Repository | `ForecastGuard` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

The GitHub environment already exists. PyPI-side registration is a separate
account action; creating the GitHub environment does not register a publisher.
Use the filename only, not `.github/workflows/publish.yml`. Trusted publishing
does not require a long-lived PyPI API token. A pending publisher does not reserve
the project name. See [PyPI's setup guide](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

The workflow rejects a tag whose commit is not on `main`, checks both source
version declarations against the tag, and runs the suite with the Nixtla extra.
It builds the wheel and sdist once, checks metadata and the isolated wheel API,
then transfers those exact artifacts to the OIDC publishing job. The publishing
job does not rebuild the package.

Prepare a draft GitHub release with curated notes while the PR is being reviewed.
Before publishing it, verify the release target is the reviewed commit on `main`
and the pending publisher is registered. A draft is not a published version.

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
