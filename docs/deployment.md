# Deployment

What a deployment repository needs to know about this component, and where the
component says it.

## The two declarations

Two files describe this project, and they are not interchangeable.

**`component.toml` is the component's statement about itself.** It is `core`: it
ships in the reference application and in every component materialized from it,
so a component always has it. It carries

- `adopted_apps` — the reusable applications this component has adopted, in the
  order the settings composition applies them;
- `selected_features` — which of `celery`, `redis` and `storage` this
  combination selected;
- `[[databases]]` — per alias, whether the database is required and which
  release-stage migration steps to run before new pods serve;
- `[[processes]]` — the process group, with each process's replica count and
  replacement strategy;
- `[[admin_processes]]` — administrative processes, which are deliberately
  *outside* the process group and never declare `COMPONENT_PROCESS`.

**`accelerator.toml` is the accelerator's knowledge about all components.** It is
`machinery`: it stays in this repository and never travels. It carries feature
surfaces, input dispositions, parameter sites, presets, the closed contributable
surface and the pinned verification subset.

The rule for placing anything new:

> A rule the component must obey at **runtime or deploy time** goes in
> `component.toml`. A rule **only the materializer needs** goes in
> `accelerator.toml`.

The reason is not tidiness. `accelerator.toml` does not travel, so a runtime rule
written there is a rule a materialized component cannot read — it would be unable
to adopt a reusable app, declare an extra migration step, or state that a
database is optional, because every one of those rules lived in a file it does
not have. Conversely, a disposition or a preset written into `component.toml`
would ship a materializer concern to every component and give the accelerator two
places to look.

`tests/unit/test_component_declaration.py` enforces the split mechanically: the
top-level key set of `component.toml` must be a subset of `component`,
`adopted_apps`, `selected_features`, `databases`, `processes` and
`admin_processes`. Anything else fails the gate.

`selected_features` is the one entry that looks like an accelerator concern and
is not. The accelerator declares what each feature *is*; `component.toml`
declares which ones *this component has*, and it is the only declaration of that
present when settings are imported in both the reference application and a
materialized component.

## Reading the declaration

`config.component.load_component_declaration()` parses the file into frozen
records and refuses anything malformed with `ImproperlyConfigured`. It resolves
`component.toml` from its own location rather than from a setting, and imports no
Django settings module, because the settings composition itself is one of its
callers.

The resolution walks up from the loader module — `component/` → `config/` →
`src/` → the directory holding `component.toml`. That holds in the source tree
and in the editable install the component runs from under `pixi run`, which is
where every consumer reads it today. It does **not** hold in a non-editable
install: the wheel is built with `only-include = ["src"]` and the sdist does not
list `component.toml` either, so a component installed from a built distribution
has nothing at that path and the loader raises its ordinary missing-file refusal.
Packaging the declaration into a built distribution is Story 5.6's call — the
component is a payload there — and it is deliberately not settled here.

```python
from config.component import load_component_declaration

declaration = load_component_declaration()
declaration.selected_features  # frozenset({"celery", "redis", "storage"})
declaration.databases[0].migrate  # ("migrate --database default --noinput",)
```

Because `component.toml` is a `core` file that carries lines belonging to a
single feature — the `worker` and `beat` processes exist only where `celery` is
selected — those lines sit inside paired `# feature:celery` / `# /feature:celery`
line comments. That is the only mechanism permitted for removing part of a `core`
file, and it is what will keep the process declarations in step with the pixi
tasks in every combination once Story 5.2 adds those tasks and the two-way gate
test that reconciles the two.

The rule for the process group is that each member declares `COMPONENT_PROCESS`
through the pixi task its `task` field names. Story 5.2 owns that half; the
entries in `component.toml` today name tasks `pixi.toml` does not yet define.
