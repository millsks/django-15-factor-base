# Epic 5 Context: Deployable unmodified — the contract to the deployment repository

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

A component must be handable, unmodified, to a deployment repository that nobody on this team owns or can edit. That repository needs to know which processes the component runs, what its probes mean, how it drains, and that migration is a release-stage step the component will never perform itself — and it must learn all of that from the component itself, not from documentation or from a file that stays behind in the accelerator. This epic creates the component's self-declaration, the process model, the two health endpoints, the drain ordering, the migration boundary, the payload properties (environment-only configuration, arbitrary non-root UID, no writable path), and the explicit database-backed session engine. It is also a precondition for the extension model: the adopted-application list and per-database migration steps a later epic depends on only become expressible here.

## Stories

- Story 5.1: The component declares itself in component.toml
- Story 5.2: The process model is declared as pixi tasks with its constraints as data
- Story 5.3: Two asymmetric health endpoints
- Story 5.4: Shutdown drains in a defined order
- Story 5.5: Migrations are a release-stage step the component never performs
- Story 5.6: The component is a payload that runs as an arbitrary non-root user
- Story 5.7: Sessions are database-backed with the engine set explicitly

## Requirements & Constraints

- **Configuration is exclusively environmental.** No configuration file is present in a built image; the component starts from environment variables alone.
- **Arbitrary non-root UID, read-only root filesystem.** The component declares no writable path beyond a temporary directory, and this is asserted rather than assumed — static files collected at build and served by the application, user media a non-goal, logs to the event stream, sessions in the database.
- **The process model is declared per combination.** `web` in all six combinations; `worker` and `beat` only where background task processing is selected. `beat` is exactly one replica (its schedule lives in PostgreSQL, so it is replaceable but not duplicable) and must be replaced stop-before-start, because a default rolling update would open exactly the two-replica window the replica count forbids.
- **Migrations never run from the component.** No entrypoint, task or container command migrates; a serving process refuses to start against an unrecognized schema. Documentation states that the pipeline migrates before new pods serve, once per declared database.
- **Two asymmetric health endpoints.** Liveness touches nothing external — a liveness probe that queries the database converts a brief outage into an estate-wide crash loop. Readiness checks that every required database answers, returns non-200 from process start until first successful contact, and never re-checks migrations, because a rolling deploy legitimately runs an older replica against a newer schema.
- **Drain ordering is the component's; the grace period is not.** On `SIGTERM` readiness flips before the drain begins, then connections stop, in-flight requests finish, and the process exits; a worker finishes its current task and declines new ones. The grace-period value is a deployment-repository setting.
- **Sessions are database-backed with the engine set explicitly** and identical in every combination — session behaviour must never be a property of an unrelated feature toggle.
- **Success criterion boundary.** The "deployable unmodified" criterion cannot be closed in this repository: deployment configuration lives elsewhere and starting a component on the target platform is out of scope. This epic delivers the component-side half only; do not claim the criterion proven.

## Technical Decisions

- **Two declaration files, one rule for placing anything.** A rule the component must obey at runtime or deploy time goes in the component's own declaration, which is `core` and always travels; a rule only the materializer needs goes in the accelerator's declaration, which never travels. The component declaration carries the adopted-application list, per-database requiredness, per-database release-stage migration steps, the process-model constraints, and the selected-feature list. An empty adopted-application list is valid and needs no special case.
- **The component declaration is itself region-bearing.** Its process-model constraints describe process types that exist in only two of six combinations, so those blocks must sit inside declared feature-owned region markers — otherwise the two-way process gate fails in the four non-Celery combinations by naming processes with no matching task.
- **Process types are pixi tasks, not a Procfile.** The deployment repository invokes `pixi run <process>` and enumerates with `pixi task list`. `worker` and `beat` are feature-owned regions of the task file — pruning them is sub-file removal by marker, not something that happens for free.
- **The gate test on the process model is two-way:** every declared process type has a matching task, and every task in the process group is named by the declaration.
- **Runtime and process-type declaration mechanics.** Process tasks set the process-type variable in their own task `env` and set no runtime, thereby inheriting *deployed*. The process-type variable may not appear in any activation env — one there would make every management command declare itself a serving process and deadlock the release stage on the migrations refusal. Locality fails closed (absent means deployed); process type fails open (absent means not a serving process). The accepted price is that a serving process started outside the `web` task does not fire the migrations refusal.
- **Payload, not image.** Materialized components ship no Dockerfile; the buildpack and golden-base path is the default. This repository ships one Dockerfile classified as machinery, purely so the harness can verify the payload properties. It does not exist yet.
- **Readiness and contributed databases.** A contributed database is treated as required unless the component declaration says otherwise; the readiness check iterates every configured database.
- **Pruning is an admin process, not a background task.** Expired session rows and expired mapper epoch records are pruned by one declared admin process, because background task processing exists in only two of six combinations. Scheduling that process belongs to the deployment repository; the component-side declaration and documentation are in scope here.
- **Health routes are greenfield.** No health route exists today — both endpoints are built, not adapted.

## Cross-Story Dependencies

- **Within the epic:** the component declaration (5.1) must land before the process-model constraints that live in it (5.2). Readiness (5.3) must exist before the drain can flip it (5.4). The zero-writable-path assertion (5.6) depends on the explicit database-backed session engine (5.7).
- **On earlier epics:** the migrations story consumes the stage-2 startup refusal built in the refusal-contract epic — it does not re-implement it. The runtime/process-type variable convention comes from the local-development epic. The epoch records pruned alongside sessions come from the authentication epic's mapper.
- **On later epics:** the feature-owned region markers used by the process tasks and the component declaration are formalized by the feature-extraction epic; declare regions in the shape that epic specifies rather than inventing a local mechanism. The materializer epic consumes those regions, and the extension-model epic depends on the adopted-application list and per-database migration steps created here.
