# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-19

### ⚙️ Miscellaneous Tasks

- Adopt the shared GitHub automation setup
- Align ci.yml with the shared workflow
- Pin pixi 0.70.2 across the project
- Update python version matrix to include 3.12, 3.13, and 3.14
- Enforce a 120-character line length in ruff
- Ignore COM812, which conflicts with the ruff formatter
- Add the verification-gap review hunter
- Record the deferred follow-up review for story 1.2
- Record the final revision for story 1.4
- Record the final revision for story 1.4's follow-up review
- Finalize story 1.4 and record its deferred follow-up review
- Finalize story 1.5 in the sprint record
- Finalize story 1.6 in the sprint record
- Finalize story 1.7 in the sprint record
- Finalize story 1.8 in the sprint record
- Finalize story 1.9 in the sprint record
- Finalize story 2.1 in the sprint record
- Finalize story 2.2 in the sprint record
- Record story 2.4's final revision in the spec
- **story-3.1**: Re-arm after resolving the AD-13 intent gap
- **sprint**: Mark story 3.7 done

### ⭐ Features

- Initial setup and configuration of the BMAD Method
- Initial setup and config of cookiecutter-django
- Restructure into src layout and adopt pixi toolchain
- Add structured logging and OpenTelemetry tracing
- Consolidate the quality gate onto one invocation
- Run the quality gate against PostgreSQL
- Delete the network surface beneath Django's routing
- Make strict type checking a gate condition
- Make the coverage floor one constant and close its measurement
- Declare the import root in exactly one place
- Close the package index to third-party packages
- Prove object-storage fitness before committing to the feature
- Move Django to the 5.2 LTS release
- **users**: Carry the identity key on the user model
- **auth**: Read the claims contract from the environment
- **users**: Provision the designated groups before the first authentication
- **auth**: Resolve an identity to a user through one mapper
- **auth**: Sync authorization once per credential epoch
- **auth**: Authenticate a person interactively against the IdP
- **auth**: Authenticate an API client programmatically against the IdP
- **locality**: Declare locality by the pixi environment
- **local**: Hold the database, cache and task substitutions locally
- **local-dev**: Seed personas from declared claims
- **local-dev**: Expose persona sign-in as a URL route driving the real mapper
- **local-dev**: Validate the local programmatic flow for real
- **observability**: Make the local non-substitution enforceable
- **local-dev**: Prove nothing on the local start path reaches the network
- **startup**: Give the refusal contract one home and two evaluation stages
- **docs**: Add technology stack documentation with framework and library details
- **startup**: Evaluate five unconditional refusals at settings import
- **startup**: Evaluate three unconditional refusals at serving-process startup
- **startup**: Scope two refusals to the features that own them

### 🐛 Bug Fixes

- Gate the debug apps behind DJANGO_DEBUG_APPS
- Trace ASGI requests and read .env before telemetry
- Harden the gate consolidation against code review findings
- Harden the PostgreSQL gate against a second review pass
- Enforce the PostgreSQL gate's own prohibition
- Pin the gate's PostgreSQL to 17
- Correct the below-resolver exception list and harden story 1.4's guards
- Assert story 1.4's AD-16 claims where they can actually fail
- Re-record the R-1 verdict against the 5.2 LTS runtime
- **tests**: Assert idp_subject uniqueness by existence, not universality
- **hooks**: Run hygiene hooks only at the pre-commit stage

### 📚 Documentation

- Add product brief for the accelerator template
- Define the local development contract in the product brief
- Audit the fifteen factors and name the parity trade-off
- Settle factors 5, 6, 8 and 9 in the deployment interface
- Close five open items ahead of the PRD
- Settle phase-2 verification, naming and the shared mapper
- Close the last open decision and the fork the Vision hid
- Add phase-1 PRD for the reference application and verification harness
- Reconcile the brief and PRD with decisions made after they were written
- Add the phase-1 architecture spine
- Reconcile the PRD with the phase-1 architecture spine
- Reconcile the architecture spine's divergences and binds range
- Add the phase-1 spec kernel
- Add the phase-1 epic breakdown and readiness assessment
- Add the phase-1 sprint plan and all 68 story files
- Record the spine corrections found during story creation
- Make the interface mechanism core and reduce to three features
- Amend the PRD and epics for three features and six combinations
- Correct four stale counts the revision-3 pass missed
- WIP partial story reconciliation for epics 7, 8 and 9
- Amend Epic 4's acceptance criteria for the leaf-module rule
- Amend Epic 8's criteria and correct AD-25's production.py ranges
- Reconcile epics 6, 8 and 9 stories, and fix Story 9.4's AC
- Reconcile Epic 7 stories and amend its epic source
- Amend the spec kernel and close the findings review
- Record the implementation revision on story 1.2
- Record the follow-up review revision on story 1.2
- Record the third review revision on story 1.2
- Add story 1.9, moving Django to the LTS release
- **auth**: Decide where a deactivated user is refused
- **story-3.1**: Record the intent gap in AD-13's local-task partition
- **arch**: Declare locality by the dev environment, not per pixi task
- **story-3.3,3.5**: Correct the locality instructions for the amended AD-13
- **story-3.7**: Record the final revision
- **story-4.1**: Import the delivered locality reader instead of a second one

### 📦 Build

- Source the commit-msg hook from conda-forge
- Switch to hatchling and measure template coverage
- Split runtime and development environments
- Give every pixi task a description and default-environment
- Trim dead dependencies and remove MFA
- Restrict Python version to 3.14 in CI configuration

### 🚜 Refactor

- **auth**: Remove the static-token credential surface entirely

<!-- generated by git-cliff -->
