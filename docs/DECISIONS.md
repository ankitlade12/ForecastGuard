# Engineering Decisions

Living log of engineering judgment. Dated entries; newest decisions may
supersede older ones (noted explicitly when they do). The PRD wins on product
intent; this log wins on implementation mechanics.

Entries preserve the decisions and scope at their dates. D-014 qualifies the
original absolute leakage claims; D-015 supersedes single-window limits;
D-016/D-018 deliver adapters and explanation hints deferred by D-008; and D-023
adds direct Python inputs. Use the architecture and API guides for current
behavior, rather than reading an early entry as the current feature list.

---

### D-001 — Nixtla-native data contract
**2026-06-14 · Accepted**

The canonical data shape is long-format `unique_id` / `ds` / `y`, matching the
Nixtla stack the tool is built for. Column names are configurable on
`ForecastSpec` (`id_col` / `time_col` / `target_col`) but default to the Nixtla
names. No check may hardcode column names.

**Why:** the wedge is the Nixtla ecosystem; aligning the contract removes
adoption friction and makes the `cross_validation` tutorial PR natural.

---

### D-002 — Three deliberately narrow checks; honest scope
**2026-06-14 · Accepted**

Ship exactly three checks — cutoff integrity, known-future covariates, runtime
leakage. The tool detects *common, high-impact* pipeline errors, not "all
leakage." We advertise this honestly.

**Why:** a narrow gate with zero false positives is trusted and adopted; an
"everything detector" with false positives gets disabled. Trust is the product.

---

### D-003 — Behavioural perturbation for leakage, not source parsing
**2026-06-14 · Accepted**

The runtime-leakage check (the moat) re-runs the user's feature function on
future-masked data and diffs the pre-cutoff values. It does **not** parse the
user's source code.

**Why:** a leak-free feature at time `t` cannot change when the future is
hidden — this is a behavioural invariant. It catches leaks AST analysis misses
(dynamic code, library internals) and never false-positives on a correctly
built trailing feature. The AST "hint layer" is a *later* additive explanation
aid (see D-008), never the detector.

---

### D-004 — Check protocol + stub pattern
**2026-06-14 · Accepted**

Every check implements the `Check` protocol and depends only on `CheckContext`
(loaded frame + spec + resolved feature function) — never on file IO. Each check
ships as a stub (a loud `SKIPPED`) before its logic lands, so the runner, CLI,
and test harness are buildable and testable from Slice 1.

**Why:** mirrors GoldMind's connector/parser protocol-and-stub discipline;
keeps slices independently shippable and the surface area stable.

---

### D-005 — Structured outputs everywhere
**2026-06-14 · Accepted**

Checks return typed `CheckResult` payloads (`pass` / `fail` / `skipped` /
`error`) carrying structured `Violation`s with a stable `code` and `evidence`
dict. No check returns free text.

**Why:** the CLI, the GitHub Action annotations, and the future hosted tier all
render the same typed contract. Codes enable selective suppression later.

---

### D-006 — Skip loudly, never pass silently
**2026-06-14 · Accepted**

When a check's precondition is missing — most importantly, the runtime check
with no `feature_fn` — it returns `SKIPPED` with a required reason, rendered
prominently. It is neither pass nor fail.

**Why:** a silent green check on an unvalidated pipeline is worse than no check;
it manufactures false confidence. Honesty is the differentiator.

---

### D-007 — The exit code is the gate
**2026-06-14 · Accepted**

`Report.exit_code()` returns `1` on any `fail`/`error`; `0` otherwise. `--strict`
promotes loud skips to `1`. The exit code is the contract CI consumes.

**Why:** the entire product is "block the agent from trusting an inflated
backtest." That block is a non-zero exit. `--strict` lets teams demand the
runtime check actually ran.

---

### D-008 — OSS CLI first; adapters and AST hints later
**2026-06-14 · Accepted**

Ship an OSS CLI + GitHub Action first. Defer: hosted CI tier,
MLForecast/StatsForecast adapters, and the AST hint layer (line-level
explanations). The adapters and hint layer are additive; they are not the
detector.

**Why:** distribution and trust are won in the open before monetization. The
SaaS tier rides on an already-trusted gate.

---

### D-009 — Click CLI, pandas core, minimal deps
**2026-06-14 · Accepted**

Runtime deps: `pydantic` (contract), `click` (CLI), `pandas` (dataframe
checks), `pyyaml` (spec loading). `pyarrow` is an optional extra for parquet.

**Why:** pandas is unavoidable for the dataframe checks; everything else is kept
minimal so the gate is cheap to install in any CI image. Click over Typer keeps
the dependency surface ubiquitous and battle-tested.

---

### D-010 — Distribution as CLI + composite GitHub Action
**2026-06-14 · Accepted**

The GitHub Action (`action.yml`) is a thin composite wrapper that installs the
package and runs `forecastguard run`. One implementation, two front doors.

**Why:** avoids a divergent second codebase; the Action inherits every check and
exit-code guarantee the CLI has.

---

### D-011 — Cutoff-integrity semantics (single-cutoff holdout)
**2026-06-14 · Accepted**

The cutoff check (Slice 2) treats `spec.cutoff` as a single train/holdout
boundary. Per series: **train** = rows with `ds <= cutoff`, **holdout** = rows
with `ds > cutoff`. A well-formed series has training history and a holdout equal
to exactly the `horizon` grid points after the cutoff on `spec.freq`
(`cutoff + 1·Δ … cutoff + horizon·Δ`).

Anchoring the expected window on the **cutoff** (not on the last training row) is
deliberate: a gap *before* the cutoff is a training-data quality issue, not a
cutoff-integrity one, so anchoring on the cutoff avoids false-positiving on it.
This assumes the cutoff is an on-grid boundary — the standard Nixtla usage, where
the cutoff is the last in-sample timestamp.

Violation codes: `FG-CUTOFF-001` duplicate `(id, ds)` (CRITICAL); `-002` no
training history; `-003` empty holdout; `-004` holdout ≠ horizon grid
(`too_few` / `too_many` / `misaligned`); `-010/011/012/013` structural guards
(missing column, unparseable timestamps, invalid freq/cutoff, empty dataset).
Per-series output is capped at 50 with an INFO overflow summary (`-099`).

**Why:** zero false positives is the trust bar (D-002). Every code is an
unambiguous, deterministic, structurally-wrong condition; ambiguous-but-maybe-ok
conditions (pre-cutoff training gaps) are intentionally not flagged.

**Out of scope (documented honestly):** off-grid cutoffs, per-series cutoffs /
rolling-origin multi-window CV, and irregular-by-design series. Revisit when a
real workflow needs them.

---

### D-012 — Known-future is a contract check, not a behavioural one
**2026-06-14 · Accepted**

The known-future check (Slice 3) validates `spec.future_covariates` against the
data; it does NOT try to infer leakage from covariate values.

Rationale: in a historical backtest panel you cannot distinguish a future
covariate (a planned promo) from a past one (actual weather) — both have values
after the cutoff, because the backtest needs those actuals to score against. So a
rule like "undeclared covariate has post-cutoff values → leak" would
false-positive on every legitimate past covariate. The *behavioural* proof that a
covariate actually leaks is the runtime check (D-003, Slice 4); Slice 3 only
validates the declared contract and surfaces the undeclared covariates.

Violations (both HIGH → FAIL): `FG-FUTURE-001` declared future covariate isn't a
column; `FG-FUTURE-002` declared future covariate has no values anywhere in the
holdout window. Undeclared covariate columns are reported as "past-only" in the
PASS summary, never as failures. Timestamp/cutoff parsing problems are owned by
the cutoff check (D-011); the known-future check declines to evaluate holdout
coverage rather than double-reporting.

Partial holdout coverage was originally out of scope and is now validated by
`FG-FUTURE-003` under D-014.

---

### D-013 — Runtime leakage via behavioural perturbation
**2026-06-14 · Accepted**

The runtime check (Slice 4, the moat) proves leakage *behaviourally*, never by
parsing source (D-003). It builds a future-masked copy of the frame, re-runs
`spec.feature_fn`, and diffs the pre-cutoff feature values against the full-frame
computation. Any pre-cutoff value that moves read across the cutoff.

The mask is **contract-aware** (ties to D-012): in future rows it preserves id,
time, declared `future_covariates`, and `static_covariates` (genuinely known at
predict time) and NaNs the target + every other (past-only) covariate. So a
forward-looking feature over a *declared* future covariate is not flagged (zero
FP), while one over an undeclared/past covariate is — the declaration drives the
perturbation.

Guards — all **SKIP loudly**, never a silent pass: no `feature_fn`; no holdout to
hide; the function raising; an output that isn't a DataFrame carrying unique
`(id, ds)` rows; or a nondeterministic `feature_fn` (detected by running it twice
on the full frame and diffing). Numeric comparison uses `np.isclose`
(rtol 1e-5, atol 1e-8, equal_nan) so benign float reordering of a correct trailing
feature never trips.

`feature_fn` is imported from the working directory and the spec file's directory
(both added to `sys.path`); its output must include the id and time columns so
rows align on `(id, ds)`.

Violation: `FG-LEAK-001` (CRITICAL), one per leaking feature column, with a sample
of changed `(id, ds)` rows and their full-vs-masked values.

**Out of scope (honest):** sub-tolerance leaks; leaks that don't move any value on
the available pre-cutoff rows; and per-window rolling-origin (multi-cutoff)
masking.

---

### D-014 — Bounded perturbation claims and a stricter availability contract
**2026-08-30 · Accepted**

Runtime leakage is a one-sided behavioural test. If censoring future-unknown
inputs changes a pre-cutoff feature, that change establishes a dependency on
future information. If nothing changes, the result means only that no
sensitivity was detected for the tested cutoff, mask, data, and numeric
tolerance. PASS summaries and current product documentation use this bounded
language; they do not claim a universal proof of no leakage. This qualification
supersedes absolute wording in D-002/D-003 without changing behavioural
perturbation as the detector.

The availability contract is also tightened before runtime masking trusts it:

- null series identifiers fail as `FG-CUTOFF-014`;
- declared future/static roles may not overlap reserved columns or each other;
- duplicate role declarations are rejected at the typed spec boundary;
- declared static columns must exist (`FG-STATIC-001`) and remain invariant
  within each series (`FG-STATIC-002`);
- declared future columns require complete coverage across available holdout
  rows (`FG-FUTURE-003` for partial coverage; `FG-FUTURE-002` for none).

Serialized reports carry `schema_version = "1.0"`; `--format json` writes only
that report to stdout while retaining the same exit-code gate.

**Why:** trust requires both high-precision failures and honest PASS semantics.
The runtime mask must not preserve a column merely because an invalid static or
future declaration told it to do so, and CI consumers need a stable structured
contract rather than scraping terminal text.

---

### D-015 — One explicit validation-window source
**2026-08-30 · Accepted**

`ForecastSpec` requires exactly one of `cutoff`, `cutoffs`, or `cutoff_col`.
Legacy `cutoff` retains its all-post-cutoff holdout semantics. Rolling raw
history bounds every origin to `horizon` grid points, allowing later history in
the same frame. `cutoff_col` validates materialized Nixtla CV output by unique
`(id, cutoff, ds)` keys and exact per-series grids. Every rolling violation
carries its origin in `location` and structured evidence.

**Why:** a forecasting gate that only checks one split does not protect the
rolling-origin evidence model-selection systems actually consume. Explicit
mutually-exclusive shapes avoid guessing.

---

### D-016 — Fitted MLForecast usage closes the declaration gap
**2026-08-30 · Accepted**

The optional MLForecast adapter obtains a fitted object from `model_path` or
`model_fn` and intersects `ts.features_order_` with raw dataframe columns. A raw
feature the model consumes but the spec does not declare future/static fails as
`FG-FUTURE-004`. Adapter loading remains at the runner IO boundary; checks see
only typed `AdapterUsage` or a loud adapter error.

**Why:** presence and user declarations alone cannot prove what the fitted model
uses. Framework evidence makes that contract checkable without coupling checks
to model IO.

---

### D-017 — Forecast outputs are a second behavioural boundary
**2026-08-30 · Accepted**

An optional `forecast_fn(train_df, future_df)` is run twice for determinism and
then against contract-aware future perturbations. Prediction changes fail as
`FG-FORECAST-001`, with origin, mode, prediction column, and row samples. This
catches direct actual-future exogenous use and teacher forcing that may not
appear in a standalone feature function. It remains a component of the third
registered check, preserving the three-check public architecture.

---

### D-018 — Availability is point-in-time; AST is explanation only
**2026-08-30 · Accepted**

Future covariates can declare an explicit availability timestamp column. A
value must be available by its historical event time and by every forecast
origin where it is consumed (`FG-AVAIL-001/002`). Runtime probes support seeded
`nullify`, `noise`, and `sign_flip` modes. AST inspection recognizes a small set
of risky constructs only after behavioural sensitivity exists and may add a
file/line hint; it never affects status.

**Why:** point-in-time truth removes ambiguity around values such as actual
weather, while multiple deterministic interventions improve behavioural
evidence. Keeping source parsing non-authoritative preserves D-003.

---

### D-019 — One Report, multiple CI renderers; pandas remains the backend
**2026-08-30 · Accepted**

Human output, versioned JSON, SARIF 2.1.0, GitHub annotations, and the step
summary all render the same typed `Report`; the exit code remains the gate. The
public mutation corpus currently scores 7/7. After replacing repeated full-frame
series filtering with one grouping pass, the reference scale run processed
365,000 rows in 2.14s (~171k rows/s), above the recorded 50k rows/s threshold.
Polars is therefore not added.

**Why:** CI integrations must not develop divergent verdict logic, and another
dataframe backend is complexity without measured need.

---

### D-020 — Setup and planning never infer availability or execute user code
**2026-09-12 · Accepted**

`init` suggests structural mappings but requires explicit future/static roles.
Generated MLForecast wrappers use a labelled reference model or a supplied
unfitted model factory. `plan` loads data and revision sidecars only; READY is
static readiness, not a runtime verdict. Coverage is per configured boundary,
origin and mode, with counts of actual executions and explicit scope notes.

### D-021 — Diagnostics are bounded explanations; replay expands the boundary
**2026-09-12 · Accepted**

Single-input diagnostic probes run only after behavioural failures, with a
separate cap constrained by remaining total runtime calls. They never create,
clear or replace a gate verdict. `pipeline_factory` creates a fresh object for
each execution and receives raw history plus the current horizon, bringing
preprocessing/fitting inside the probe when implemented there. Consecutive
singleton reuse skips. This is not process or external-state isolation.

### D-022 — Revision histories enforce an explicit latest-available policy
**2026-09-12 · Accepted**

Revision sidecars use spec identity/time columns and configurable value/publication
columns. At each origin, compare supplied training inputs and declared future
horizon inputs to the latest published version. Scoring targets are excluded.
Missing publication evidence, ambiguity and mismatches are distinct outcomes.
The check is composed into known-future validation and never repairs data.
Stale versions also fail this declared policy; that is a snapshot-contract
violation, not universal behavioural evidence of future leakage.

---

### D-023 — Direct Python inputs share the existing runner
**2026-09-19 · Accepted**

The package exports `run_checks` and accepts a DataFrame and Python callable
objects as keyword-only execution inputs. `ForecastSpec` remains serializable;
`data` is optional for in-memory API use, while YAML loading still requires
a path. Explicit frames take precedence over paths. Duplicate reference/object
sources are rejected, and replay is mutually exclusive with feature/forecast
boundaries across both input forms.

Direct inputs use the same prerequisite ordering, budgets, diagnostics, coverage
and checks as file-based execution. Perturbation still requires an explicit
window and callable. Revision sidecars and fitted-model adapters retain their
existing contracts.

**2026-09-19 clarification:** revision identity uses exact stored-value equality,
not the relative floating-point tolerance used for runtime predictions. Inputs
and sidecars must use consistent numeric representations. This prevents large
values from hiding a distinct revision within a proportional tolerance.
