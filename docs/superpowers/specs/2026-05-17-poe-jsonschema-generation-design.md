# JSON Schema Generation for poethepoet Config — Design

**Status:** Drafted 2026-05-17, pending review.
**Author:** Initial design produced collaboratively with Claude.

## 1. Goals and scope

### Primary goal

Auto-generate `partial-poe.json` — the JSON Schema for the `tool.poe` subtable inside `pyproject.toml` — directly from the `PoeOptions` class definitions, so it can replace the existing community-contributed entry on schemastore.org on every poe release.

The schema is consumed by editor integrations (most notably the VS Code Python/TOML tooling that loads pyproject.toml schemas via schemastore's catalog). The existing schemastore `pyproject.json` references our schema via `$ref` at `properties.tool.properties.poe`. Our generated file must be a self-contained JSON Schema describing the `tool.poe` block.

### In scope (first pass)

- One generated schema: `docs/_static/partial-poe.json` (draft-07, matching the current entry's draft level and matching the directory used by Sphinx docs).
- A `__schema_fragment__()` class method on `PoeOptions` (with a sensible default implementation), overridable by subclasses where defaults can't express the required shape.
- Per-class docstring extraction via `ast`, so class-attribute docstrings become JSON Schema `description` properties.
- `additionalProperties: false` everywhere structural. A single deliberate exception: a forward-compat fallback branch for task dicts that don't match any known task-type discriminator key.
- Full parity test suite under `tests/schema/`, gated by a `pytest.mark.schema` marker auto-applied via `conftest.py`.
- A `poe build-schema` task; a CI drift check; a `poe test-schema` task; integration with `poe check`.
- Cleanup-first work in `PoeOptions`: tighten runtime-validated string options to `Literal[...]` where the set is static, add new `Metadata` constraint fields (`pattern`, `examples`, `minimum`, `maximum`, `min_length`, `max_length`) that serve both runtime validation and schema generation.

### Deferred

- Standalone schemas for `poe_tasks.{toml,yaml,json}` and for included config files (secondary goal noted by the maintainer).
- Automation for opening PRs to schemastore.org on release (manual submit per release is fine for now).
- Integration of `poe build-schema` into the existing `poe bump-version` flow (the maintainer will wire this in themselves).

### Out of scope

- Replacing or significantly extending `PoeOptions` runtime validation beyond what the new `Metadata` constraint fields require.
- Generating TypeScript types, documentation pages, or any artifact other than `partial-poe.json` from the same source.
- Editor or LSP integrations beyond what `schemastore` enables transitively.

## 2. Module layout and architecture

### Package structure

```
poethepoet/schema/
├── __init__.py        # public API: build_schema() -> dict
├── __main__.py        # python -m poethepoet.schema → writes docs/_static/partial-poe.json
├── context.py         # SchemaContext: definitions registry + description routing for PoeOptions and TypedDicts
├── generator.py       # orchestrator: walks PoeOptions classes, calls hooks, assembles root schema
├── translate.py       # TypeAnnotation → JSON Schema primitive translator
└── fragments.py       # cross-cutting helpers (env_option, executor union, task fallback branch)
```

AST-based docstring extraction lives in `poethepoet/options/_docstrings.py` (introduced in Phase 1). The schema package's `context.py` routes description lookups to either `PoeOptions.description_for_field` (for `PoeOptions` subclasses) or `extract_field_descriptions` (for TypedDicts) — addressing the Section 7 risk about emission-path divergence in one place.

The package lives inside `poethepoet/` (not under `scripts/`) so it is importable from tests and so it can be extended later for the deferred secondary schemas. The package is **never imported during normal CLI invocations** — only by `poe build-schema` and by schema tests — so it has zero impact on CLI startup performance.

### Type translation

`translate.py` is a generic translator with no domain knowledge:

| TypeAnnotation | JSON Schema output |
|---|---|
| `PrimitiveType(str/int/float/bool)` | `{"type": ...}` (with `pattern`/`minimum`/etc. layered in from Metadata) |
| `LiteralType` | `{"enum": [...]}` (with `type:` if all values share one) |
| `ListType` | `{"type": "array", "items": ...}` (with `minItems` etc. from Metadata) |
| `DictType` | `{"type": "object", "additionalProperties": <value schema>}` |
| `TypedDictType` | `{"type": "object", "properties": ..., "required": ..., "additionalProperties": false}` |
| `UnionType` (plain) | `{"anyOf": [...]}` |
| `UnionType` (tagged) | `{"oneOf": [...]}` — used when the orchestrator knows there's a discriminator |
| `UnionType` with `NoneType` | the `NoneType` branch is removed and the field becomes optional at the parent level |
| `AnyType` | `{}` (matches anything) |
| `NoneType` | handled inside Union resolution; never emitted standalone |

### Generator orchestrator

`generator.py` builds the root schema and is the only place that knows about cross-cutting compositions the type system doesn't natively encode:

1. Walk `ProjectConfig.ConfigOptions.get_fields()`, translate each via `translate.py`, layer in docstrings.
2. Assemble the **task_def polymorphism** (string / list / dict-with-discriminator / forward-compat fallback) used wherever a "task definition" position appears (inside `tasks`, `groups.*.tasks`, sequence/parallel/switch sub-items).
3. Assemble the **executor tagged union** (over the `type:` field) by walking the registered `PoeExecutor` subclasses.
4. Assemble the **env value polymorphism** (`str | EnvDefault`) and the **envfile polymorphism** (`str | Sequence[str] | EnvfileOption`).
5. Emit `definitions` for shared shapes (`task_def`, `executor_option`, `env_option`, `envfile_option`, `args_item`, etc.). Property schemas inside variant definitions either reference these by `$ref` or inline them — see section 3 for the rule.
6. Output a fully self-contained draft-07 schema with `$id: https://json.schemastore.org/partial-poe.json` and a `$comment` recording the poe version that produced it.

The orchestrator output is deterministic (keys sorted, trailing newline) so diffs are stable.

## 3. Polymorphism and composition handling

### The `__schema_fragment__` hook

A single hook, defined on `PoeOptions` with a default implementation and overridable at any level of the class hierarchy:

```python
class PoeOptions:
    @classmethod
    def __schema_fragment__(cls, ctx: SchemaContext) -> dict:
        """Emit a JSON Schema fragment describing this options dict."""
        # Default: translate every field via translate.py, attach docstrings,
        # set additionalProperties: false. Most classes inherit this unchanged.
```

`SchemaContext` is passed through so fragments can register definitions and resolve `$ref`s through a single shared definitions table.

#### Per-level responsibility

- **`PoeOptions.__schema_fragment__`** emits an options-dict shape: properties from the class's fields, `additionalProperties: false`, descriptions sourced from class-attribute docstrings.
- **`PoeTask.__schema_fragment__`** (overrides the default) calls `cls.TaskOptions.__schema_fragment__(ctx)` to get the options shape, then wraps it with the discriminator key (`cls.__key__`) typed by `cls.__content_type__`, and marks the discriminator as required.
- **Subclass overrides** use `super().__schema_fragment__(ctx)` to compose with the parent's shape, then mutate only the parts they need to customize.

Concrete overrides expected in the first pass:

- **`SwitchTask`** — its `switch` content is a list of dicts with an optional `case` key alongside a nested task def; the default can't express that.
- **`SequenceTask` / `ParallelTask`** — content items must reference the recursive `task_def`. The default translator would derive `items` from the Python annotation (`list[str | dict[str, Any]]` → `items: {anyOf: [{type: string}, {type: object}]}`), which is too loose. The override replaces it with `items: {$ref: "#/definitions/task_def"}`.
- **`ArgSpec`** (in `task/args.py`) — owns the per-arg shape. Already a `PoeOptions` subclass. The outer `args` option's list-vs-dict polymorphism is handled at the orchestrator level, not in `ArgSpec.__schema_fragment__` itself.

Classes that need no override: every other `TaskOptions` and `ExecutorOptions` subclass.

### Why inlining instead of `allOf` + delta

The natural-seeming approach — emit each subclass as `allOf: [{$ref: base}, {properties: own_fields}]` — is **wrong in draft-07**. The `additionalProperties: false` constraint only sees properties declared in the same subschema, not in sibling `allOf` branches, so validating a task config against `allOf: [standard_options, cmd_specific]` with `additionalProperties: false` would incorrectly reject every standard option as "additional."

Draft 2019-09's `unevaluatedProperties: false` fixes this cleanly, but using a newer draft would diverge from current schemastore conventions and may reduce editor tool compatibility.

**Resolution:** full inlining (every variant's `properties` map contains all fields, own + inherited). The generated schema grows from ~900 to ~1500 lines but `additionalProperties: false` works naturally, the generator is simpler, and editor experience is unaffected. If file size becomes a real problem later, the refinement is to extract each shared option into its own `$def` and reference by `$ref` from each variant.

### Composition the orchestrator handles directly

These are cross-cutting concerns not owned by any single PoeOptions class:

**`task_def` union** — every position where a "task" can appear (tasks map values, group task values, sequence/parallel items, switch cases):

```jsonc
"task_def": {
  "oneOf": [
    {"type": "string"},                                  // bare str → default_task_type
    {"type": "array", "items": {"$ref": "#/definitions/task_def"}},  // bare list → default_array_task_type
    {"$ref": "#/definitions/cmd_task"},
    {"$ref": "#/definitions/shell_task"},
    {"$ref": "#/definitions/script_task"},
    {"$ref": "#/definitions/expr_task"},
    {"$ref": "#/definitions/ref_task"},
    {"$ref": "#/definitions/sequence_task"},
    {"$ref": "#/definitions/parallel_task"},
    {"$ref": "#/definitions/switch_task"},
    {                                                     // forward-compat fallback
      "type": "object",
      "not": {"anyOf": [
        {"required": ["cmd"]}, {"required": ["shell"]}, {"required": ["script"]},
        {"required": ["expr"]}, {"required": ["ref"]}, {"required": ["sequence"]},
        {"required": ["parallel"]}, {"required": ["switch"]}
      ]}
    }
  ]
}
```

The fallback branch matches any dict that doesn't contain a recognized discriminator and imposes no constraints — forward compatibility for task types added in newer poe versions than the editor's schema.

**`executor_option` tagged union** — over the `type:` field (a proper tag, unlike the task-key presence discriminator):

```jsonc
"executor_option": {
  "oneOf": [
    {"type": "string", "enum": ["auto", "simple", "poetry", "uv", "virtualenv"]},  // shorthand
    {"$ref": "#/definitions/executor_auto"},
    {"$ref": "#/definitions/executor_simple"},
    {"$ref": "#/definitions/executor_poetry"},
    {"$ref": "#/definitions/executor_uv"},
    {"$ref": "#/definitions/executor_virtualenv"}
  ]
}
```

Each executor's definition is its `ExecutorOptions.__schema_fragment__(ctx)` with `properties.type: {const: <key>}` and `type` required. The enum values and the per-executor `$ref` list above are illustrative; the orchestrator generates both from `MetaPoeExecutor`'s registry at generation time, so newly registered executors appear automatically.

**`tasks` and `groups` maps** — `patternProperties` for the validated name patterns (`^[A-Za-z_][\w\-:+]*$` for tasks; `[\w\-_]+` for groups) plus `additionalProperties: false`. The patterns come from `_TASK_NAME_PATTERN` in `task/base.py` and from `ProjectConfig.ConfigOptions.validate` respectively. These are dict-key constraints, not field-value constraints, so they don't fit the per-field `Metadata` model — they stay where they are, and the Phase 2 orchestrator imports them directly from those locations to emit the `patternProperties`. (If at some point we need this in more than one place, we can extract them to module-level constants for cleaner reuse.)

**`env` map** — `additionalProperties: <env_value_schema>` where the value schema is `oneOf({type: string}, {$ref: "#/definitions/env_default"})`. Keys are unconstrained (env var names).

## 4. PoeOptions cleanup and annotation expressivity

**Principle:** *Schema constraints must be real runtime rules.* If a constraint appears in the generated schema, it must also be enforced by `PoeOptions` at parse time. This rules out schema-only annotations (no "documentation pattern that the runtime ignores"). The benefit: one source of truth, no possibility of schema/runtime drift on constraints, and contributors who add a new `Metadata` constraint know it will tighten runtime behavior.

### Cleanup items (Phase 1)

**Literal tightening** — convert runtime-validated string options to `Literal[...]` where the set is statically known:

- `ShellTask.TaskOptions.interpreter`: type becomes `ShellInterpreter | Sequence[ShellInterpreter] | None`, where `ShellInterpreter = Literal["posix", "sh", "bash", "zsh", "fish", "pwsh", "powershell", "python"]` is declared as a type alias alongside `KNOWN_SHELL_INTERPRETERS` (which becomes `get_args(ShellInterpreter)` so the tuple and the Literal stay in lockstep).
- `ProjectConfig.ConfigOptions.shell_interpreter`: same transformation.
- Both changes delete bespoke `validate()` logic; runtime validation falls out of `LiteralType.validate` automatically.
- Audit pass to catch any other runtime-validated-against-static-list cases.

Options whose accepted values come from dynamic registries (`default_task_type`, etc.) stay as plain `str` at the annotation layer; the schema generator hardcodes the `enum` from the registry at generation time.

**Metadata extensions** — add new fields to `poethepoet.options.annotations.Metadata`. Each field falls into one of two scopes with different semantics:

*Field-level metadata* describes the option as a whole (its config key, documentation hints). It applies to any field regardless of value type, and may sit on an outer `Annotated[Union[...], Metadata(...)]` wrapping a union.

| Field | Runtime behavior | Schema output |
|---|---|---|
| `config_name: str \| None` | `PoeOptions.get_fields()` uses this to map TOML keys to attribute names | (consumed at field level; no direct emission) |
| `examples: list[Any] \| None` | none (documentation-only) | `examples:` |

*Type-level metadata* constrains the runtime value. Each constraint applies to specific type kinds, so it must be attached to the matching branch via `Annotated[T, Metadata(...)]` where `T` is the concrete type — not to a surrounding union.

| Field | Applies to | Runtime behavior | Schema output |
|---|---|---|---|
| `pattern: str \| None` | string | `PrimitiveType.validate` checks `re.search` (unanchored, matching JSON Schema `pattern:` semantics) | `pattern:` |
| `minimum: int \| float \| None` | integer/number | `PrimitiveType.validate` checks lower bound | `minimum:` |
| `maximum: int \| float \| None` | integer/number | `PrimitiveType.validate` checks upper bound | `maximum:` |
| `min_length: int \| None` | string | `PrimitiveType.validate` checks character-length lower bound | `minLength:` |
| `max_length: int \| None` | string | same, upper bound | `maxLength:` |
| `min_items: int \| None` | array | `ListType.validate` checks item-count lower bound | `minItems:` |
| `max_items: int \| None` | array | same, upper bound | `maxItems:` |

**Note on the `min_length` / `min_items` split.** JSON Schema treats `minLength` (string characters) and `minItems` (array items) as separate keywords with different semantics. PoeOptions mirrors that vocabulary: `min_length`/`max_length` are exclusively string constraints; `min_items`/`max_items` are exclusively array constraints. The single-constraint conflation that would otherwise arise on `str | list[str]` (where one `min_length` would have to mean two different things) is structurally impossible — they're different fields.

**Note on `examples`:** documentation metadata, not a constraint. Conceptually the same as `config_name` (also field-level, also no runtime validation role). The principle "schema constraints must be runtime rules" applies to *constraints*, not to *metadata*. We should resist further metadata-only fields without a similar justification.

**Validation message quality:** when a constraint fails at runtime, the error message should be specific and actionable — at minimum naming the field, the constraint that failed, and the offending value. Existing custom `validate()` overrides whose work the new constraints replace likely produce better messages than a generic "`'interpreter'` does not match pattern" — the implementation must port those messages forward, not regress them.

### Annotated nesting and union-of-Annotated

`typing.Annotated` nests naturally inside `Union`. For unions where one branch needs a type-level constraint, attach `Metadata` to that branch — not to the union:

```python
# Good: min_items lives on the list branch where it makes sense.
interpreter: (
    ShellInterpreter
    | Annotated[Sequence[ShellInterpreter], Metadata(min_items=1)]
    | None
) = None

# Bad: ambiguous at the union level. Which branch does min_length mean?
interpreter: Annotated[
    ShellInterpreter | Sequence[ShellInterpreter] | None,
    Metadata(min_length=1),
] = None
```

Field-level metadata on a union remains supported and idiomatic, because it describes the *option*, not a *value*:

```python
# Good: config_name is field-level — applies regardless of which branch matches.
assert_: Annotated[bool | int, Metadata(config_name="assert")] = False
```

`UnionType` does not propagate any metadata into its child branches. The metadata stays exactly where it was authored:

- The recipient of a type-level constraint sees it directly on its own `Annotated` wrapper (no surprises from a parent union pushing constraints down into a branch the author never intended to constrain).
- Field-level metadata on `Annotated[Union[...], Metadata(...)]` remains on the `UnionType` itself for `get_fields()` to read.

### Schema-side enforcement of constraint scope

The runtime is permissive: a type-level constraint attached to a branch it doesn't apply to (e.g. `Annotated[str, Metadata(min_items=1)]`) is silently ignored — `PrimitiveType.validate` only knows about `min_length`, not `min_items`. This avoids per-parse overhead checking constraint applicability on every option, and keeps validation logic per-type local.

The schema generator (Phase 2) provides the safety net: it inspects every constraint in context with its target type, and raises a clear error if a type-level constraint is attached to an incompatible type. This catches authoring mistakes at build time — when `poe build-schema` runs — before any drift can ship.

The constraint-to-type mapping is exposed as a lazy classmethod on `Metadata`, so the schema generator looks it up at one source of truth rather than re-encoding the knowledge in a sibling module. Because the mapping is only needed during schema generation (an offline build step) — never on the CLI hot path — it's constructed on demand rather than eagerly at module import:

```python
class Metadata:
    @classmethod
    def type_constraints(cls) -> dict[str, frozenset[str]]:
        # Constructed on demand: only schema generation reads this, and that
        # runs offline. Keeping it out of the class body avoids paying the
        # construction cost on every CLI invocation. Field-level fields
        # (config_name, examples) are not listed — they apply to any field
        # regardless of value type.
        return {
            "pattern":    frozenset({"string"}),
            "minimum":    frozenset({"integer", "number"}),
            "maximum":    frozenset({"integer", "number"}),
            "min_length": frozenset({"string"}),
            "max_length": frozenset({"string"}),
            "min_items":  frozenset({"array"}),
            "max_items":  frozenset({"array"}),
        }
```

Adding a new type-level constraint is a three-line change: a slot, a kwarg, and an entry in `type_constraints()`. The schema generator picks it up automatically.

**Docstring convention** — formalize class-attribute docstrings as the source of field descriptions:

```python
class TaskOptions(PoeOptions):
    cwd: str | None = None
    """The working directory the task runs in. Relative to the project root unless absolute."""
```

Convention follows PEP 257-style attribute documentation: a string literal expression statement immediately following an `AnnAssign` in the class body. Extracted via `ast.parse` once per class, cached. Add `PoeOptions.description_for_field(name) -> str | None` helper. Handle MRO so an unset description on a subclass falls back to the parent's docstring for an inherited field.

**Description backfill** — Phase 1 also includes a backfill pass: write class-attribute docstrings for fields currently lacking them, using the existing schemastore entry's descriptions as a starting point. Without this, the generated schema would be a regression in editor tooltip quality vs. what users have today.

### What stays out of Phase 1

- Modeling the "presence of one of N keys" discriminator in the annotation layer. The pattern is awkward to express formally and the orchestrator handles it cleanly. Re-evaluate if a second motivating feature appears.

## 5. Test strategy

All schema tests live under `tests/schema/`. They're gated behind a `pytest.mark.schema` marker so `poe test` continues to run only the existing fast test suite. A dedicated `poe test-schema` task runs them.

### Layout

```
tests/schema/
├── conftest.py              # session-scoped fixtures; auto-applies pytest.mark.schema
├── fixtures/
│   ├── invalid/             # known-rejected configs (one .toml per case)
│   └── seeds/               # valid configs used as mutation starting points
├── test_meta.py             # generated schema is itself valid draft-07; structural sanity
├── test_fixture_configs.py  # every tests/fixtures/*_project config validates
├── test_invalid_corpus.py   # curated invalid configs are rejected by both schema and runtime
└── test_mutation.py         # mutate seed configs; assert schema + runtime agree
```

No `__init__.py` (matches the existing convention in `tests/options/`, `tests/env/`, etc.).

### Marker auto-application

Register the marker in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "schema: schema validation tests (excluded from default `poe test`)",
]
```

Apply it automatically — but only to the parity-test files — via `conftest.py`:

```python
# Filenames containing parity tests (slow; require the full schema build
# and the jsonschema library). Unit tests for the translator, hooks, and
# SchemaContext also live under tests/schema/ but are NOT auto-marked —
# they run on every `poe test`.
PARITY_TEST_FILES = frozenset({
    "test_meta.py",
    "test_fixture_configs.py",
    "test_invalid_corpus.py",
    "test_mutation.py",
})


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.fspath.basename in PARITY_TEST_FILES:
            item.add_marker(pytest.mark.schema)
```

Maintainers don't decorate individual tests. The marker composes — `pytest -m "schema or smoke"` works as expected. New unit-test files added under `tests/schema/` are automatically left unmarked (and therefore run in the default suite); new parity-test files need to be added to the allowlist above.

### Poe tasks

```toml
[tool.poe.tasks.test]
cmd = "pytest -m 'not schema'"

[tool.poe.tasks.test-schema]
cmd = "pytest -m schema tests/schema/"
```

The existing `poe test-quick` task also needs updating to exclude the `schema` marker. Currently it's `pytest -m 'not (slow or flaky)'`; Phase 3 changes it to:

```toml
[tool.poe.tasks.test-quick]
cmd = "pytest -m 'not (slow or flaky or schema)'"
```

`poe check` includes both `test` and `test-schema` (exact composition follows the existing `poe check` structure).

### Dependency placement

The schema generator (in `poethepoet/schema/`) emits plain dicts and has no `jsonschema` dependency. Only tests use `jsonschema` (`Draft7Validator.check_schema` for meta-validation; validator instances for parity checks). It belongs in the dev dependency group; end users never see it.

### Test specifics

- **`test_meta.py`** — `Draft7Validator.check_schema(build_schema())`; structural sanity (root has `definitions`, `additionalProperties: false`, exactly one `$schema` declaration, etc.). Also asserts that the schema builder raises a clear, named error when a type-level `Metadata` constraint is attached to an incompatible type (e.g. `Annotated[str, Metadata(min_items=1)]`), citing the field, the constraint, and the incompatible type — the safety net described in Section 4.
- **`test_fixture_configs.py`** — enumerate `tests/fixtures/*_project/` directories; find the `[tool.poe]` block (from `pyproject.toml` or `poe_tasks.*`); assert the schema accepts it. Parametrize so each fixture is its own test ID.
- **`test_invalid_corpus.py`** — each `tests/schema/fixtures/invalid/*.toml` file contains a `[tool.poe]` block plus a `# expected_error: ...` annotation line. Test asserts both: PoeOptions raises `ConfigValidationError` *and* schema validation produces at least one error.
- **`test_mutation.py`** — apply a small mutator library (delete required field, change type, replace enum value with garbage, etc.) to each seed config. Each (seed × mutator × applicable path) becomes its own parametrized test case so per-case visibility is preserved (a divergence shows up as a single failing or `xfail` test, not as one line in a multi-line failure dump). Known-divergent cases (cross-task validations the schema can't express) are wrapped in `pytest.param(..., marks=pytest.mark.xfail(reason=...))` with explicit reasons citing the relevant spec section.

### Deliberate gaps

- Cross-config rules (`deps` referencing real task names, `switch` control task type, `ref` task's "no executor", `args` cross-arg constraints) remain runtime-only. JSON Schema cannot express them. The mutation tests `xfail` these with clear reasons.
- We don't assert specific description strings — only that descriptions are present where the annotations have docstrings.

## 6. Lifecycle: regeneration and drift prevention

### `poe build-schema` task

```toml
[tool.poe.tasks.build-schema]
cmd = "python -m poethepoet.schema"
help = "Regenerate docs/_static/partial-poe.json from PoeOptions definitions"
```

`poethepoet/schema/__main__.py` writes to `docs/_static/partial-poe.json` with sorted keys and a trailing newline. Deterministic ordering is critical for stable diffs.

### CI drift check

A CI step (in the existing quality job or a dedicated `schema-drift` job) runs:

```bash
poe build-schema
git diff --exit-code docs/_static/partial-poe.json
```

On a non-empty diff, the job fails with:

> `docs/_static/partial-poe.json` is out of date. Run `poe build-schema` and commit the result.

This is the sole automated enforcement preventing drift between `PoeOptions` changes and the committed schema. If a contributor adds an option but doesn't regenerate, CI catches it on every PR.

### `poe check` integration

Both `test-schema` and the drift check participate in the umbrella quality task. Exact composition matches whatever `poe check` looks like at implementation time.

### Release flow (out of scope for this work)

The integration of `poe build-schema` into `poe bump-version` (so the release commit always contains an up-to-date schema as a safety net beyond CI) will be done by the maintainer themselves. This spec records that it's a logical follow-up but doesn't deliver it.

The maintainer-driven flow for actually publishing to schemastore (forking schemastore/schemastore, copying the file, opening a PR) is also out of scope. Long-term, this is automatable with a GitHub Action.

### Schema versioning

A `$comment` at the top of the generated schema records the producing poe version:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://json.schemastore.org/partial-poe.json",
  "$comment": "Generated by poethepoet 0.50.0. Do not edit by hand.",
  ...
}
```

The `$id` stays stable across releases so editor integrations continue to resolve.

## 7. Risks and known gaps

### Accepted tradeoffs

- **Forward-compat escape hatch hides typos.** A task dict like `{cdm = "echo foo"}` (typo of `cmd`) won't trigger a schema error — it falls into the unrecognized-task-type fallback branch. Explicit tradeoff for forward compatibility with future task types. Recorded in the generator module's docstring so future maintainers don't re-litigate.
- **Cross-cutting runtime rules aren't expressible in JSON Schema** — `deps` referencing real task names, `switch` control-task type restrictions, `ref` task's "no executor" rule, `args` cross-arg constraints. These remain runtime-only; mutation tests `xfail` each with a clear reason.
- **Schema size grows ~65%** (~900 → ~1500 lines) from full inlining. Acceptable; revisit with per-property `$ref` refinement if it becomes annoying.

### Risks worth watching during implementation

- **Docstring extraction edge cases** — multiline docstrings, conditional class bodies, MRO-aware inherited-field lookup. Pin the convention down in `CLAUDE.md` during Phase 1 so contributors know what shape of docstring is expected.
- **TypedDict vs. PoeOptions emission paths can diverge.** `IncludeItem`, `EnvDefault`, `EnvfileOption`, `TaskGroup` aren't `PoeOptions` subclasses; they're handled by the existing `TypedDictType` translator. The two paths must produce structurally consistent shapes (same `additionalProperties` defaults, same `required` handling). Mitigation: factor "emit an object schema with properties + required + additionalProperties: false" into a single helper that both paths call.
- **Runtime tightening from new Metadata constraints could break existing configs.** Adding `pattern` to `cwd` and enforcing it at runtime might reject configs that previously passed. The patterns we'd add (e.g. non-whitespace) are unlikely to be relied upon, but verify against the fixture corpus before landing each new constraint.
- **Description parity with current schema.** The existing schemastore entry has rich descriptions. Phase 1's docstring backfill must reach parity with what's there today, otherwise the generated schema would regress editor tooltip quality at v1.

### Open implementation questions

- Exact mutator library for `test_mutation.py` — start small, expand as gaps surface.
- Whether the `args` option's list-vs-dict polymorphism is best expressed via an `ArgSpec.__schema_fragment__` override or as orchestrator composition (probably orchestrator, since the polymorphism is at the *outer* `args` field, not in `ArgSpec` itself).

None are blockers.

## 8. Phasing

The work decomposes into three phases that ship independently. Each phase is reviewable and valuable on its own.

### Phase 1 — PoeOptions cleanup and annotation expressivity

- Audit and apply `Literal[...]` tightening (shell interpreters, others discovered during audit).
- Extend `Metadata` with `pattern`, `minimum`, `maximum`, `min_length`, `max_length`, `examples`.
- Implement runtime enforcement for each new constraint, with attention to validation message quality (port existing custom-validate messages forward where the new constraint replaces them).
- Implement class-attribute docstring extraction via `ast`; add `PoeOptions.description_for_field()` with MRO-aware lookup and per-class cache.
- Backfill docstrings to reach parity with current schemastore descriptions.
- Update / extend tests to cover the new `Metadata` fields and the docstring helper.

Ships independently as cleaner runtime behavior, fewer bespoke `validate()` overrides, and a more declarative annotation system.

### Phase 2 — Schema generator and parity tests

- New `poethepoet/schema/` package (`translate.py`, `generator.py`, `docstrings.py`, `fragments.py`, `__main__.py`).
- Default `PoeOptions.__schema_fragment__` implementation; override on `PoeTask`; specific overrides on `SwitchTask`, `SequenceTask`, `ParallelTask`, `ArgSpec` as needed.
- Orchestrator handles `task_def` union (incl. forward-compat fallback), executor tagged union, `env` value polymorphism, `tasks`/`groups` map shapes.
- Constraint-scope safety check: the translator consults `Metadata.type_constraints()` and raises a clear, named error if a type-level constraint is attached to an incompatible type (e.g. `min_items` on a string).
- Generated `docs/_static/partial-poe.json` committed to repo.
- Full `tests/schema/` suite (meta, fixture-configs, invalid corpus, mutation).

Ships independently as the feature itself.

### Phase 3 — Lifecycle integration

- `poe build-schema` task.
- `poe test-schema` task with marker auto-application.
- CI drift check job.
- Integration into `poe check`.

Ships independently as drift prevention infrastructure.

**Excluded:** integration with `poe bump-version`, automation of schemastore PRs. The maintainer handles these directly.
