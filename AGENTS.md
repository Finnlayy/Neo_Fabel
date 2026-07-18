# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a blank project scaffold. As code is introduced, keep implementation files under `src/`, automated tests under `tests/`, and non-code resources under `assets/`. Mirror source paths in the test tree; for example, tests for `src/core/parser.*` belong in `tests/core/`. Place project-level configuration and dependency manifests in the repository root. Do not commit generated output, dependency caches, editor metadata, or local environment files.

## Build, Test, and Development Commands

No build system, package manifest, or task runner is configured yet. The first implementation change must document its supported commands in `README.md` and expose them through the ecosystem's standard manifest or a root-level task runner. Prefer a small, stable command surface covering:

- dependency installation;
- local development or execution;
- the complete test suite and a single test;
- formatting, linting, and production builds.

Keep this section synchronized with the actual commands once tooling is added; do not document commands that cannot run from the repository root.

## Coding Style & Naming Conventions

No language-specific formatter or linter is present. Add the conventional formatter and static-analysis configuration for the selected language with the first source files, and run both before review. Use names consistent with that language's standard library and keep filenames aligned with their primary module or component. Avoid mixing unrelated formatting changes with functional work.

## Testing Guidelines

No test framework or coverage threshold is currently defined. Add tests with each behavior-bearing module and keep fixtures close to the tests that consume them. Name tests for observable behavior rather than implementation details. When a framework is selected, document suite and single-test commands above and define any coverage requirement in its checked-in configuration.

## Commit & Pull Request Guidelines

Git history is not available, so no existing commit convention can be inferred. Until one is established, use short, imperative commit subjects such as `Add configuration loader`. Pull requests should explain the purpose and approach, identify validation performed, and link relevant issues. Include screenshots only for visible interface changes, and call out configuration changes or follow-up work explicitly.

## Security & Configuration

Keep credentials and machine-specific values out of version control. Commit a sanitized example configuration when runtime settings are introduced, and document required variables without including real secrets.
