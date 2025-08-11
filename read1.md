# CircleCI Dynamic Configuration — Implementation, Issues, Fixes, and Impact

This README documents a real-world implementation of CircleCI dynamic configuration using the `path-filtering` orb and continuation workflows. It records the architecture, the problems encountered during development, the analysis, applied fixes, and the impact. The intent is to help other engineers reproduce the setup, avoid pitfalls, and understand the trade-offs.

---

## Table of contents

1. Overview
2. Goals
3. Repository layout (recommended)
4. Implementation summary
5. Problems encountered (detailed)
6. Root causes and deep analysis
7. Fixes and concrete code snippets
8. Validation & debug techniques
9. Impact of the fixes
10. Recommendations & best practices
11. How to reproduce the issue (minimal repro)
12. How I reported the doc/bug to CircleCI
13. Appendix: useful commands and examples

---

## 1. Overview

This project uses CircleCI dynamic configuration (`setup: true`) together with the `circleci/path-filtering` orb and the `continuation` orb to:

- Inspect changed files (path filtering)
- Build a small set of parameters based on mapping rules
- Generate a second (continued) configuration built from modular YAML fragments
- Continue the pipeline using the generated config and the parameters

Because the dynamic/config continuation flow is subtle, many small problems crop up in practice. This README explains the full workflow and the issues encountered, with concrete fixes.

---

## 2. Goals

- Modularize CI config into multiple YAML fragments (`.circleci/jobs/*.yml`, `workflows/*.yml`) and assemble them at runtime.
- Avoid running full pipelines on irrelevant changes by using path-filtering orb mappings.
- Use `pipeline.parameters` (booleans) to gate `when: << pipeline.parameters.some_flag >>` logic in the generated continuation config.
- Keep the main `config.yml` small: it only sets up the dynamic generation step.

---

## 3. Repository layout (recommended)

```
.circleci/
├── config.yml                # setup: true (setup workflow)
├── preprocessor.sh           # optional: local assembler for fragments
├── shared/                   # fragments packed by circleci config pack
│   ├── shared-config.yml
│   └── jobs/
│       ├── lint.yml
│       ├── test.yml
│       └── build.yml
├── jobs/                     # alternative: modular files referenced directly
│   ├── lint.yml
│   ├── test.yml
│   └── build.yml
└── workflows/
    └── build_and_release.yml
```

---

## 4. Implementation summary

Key parts of the setup:

- `config.yml` is `setup: true`. It runs a setup workflow that:

  1. Optionally runs a local `preprocessor.sh` to construct a `config_continued.yml` or a file list (`/tmp/filtered-config-list`).
  2. Calls `path-filtering/set-parameters` with a `mapping:` - this writes `/tmp/pipeline-parameters.json` and `/tmp/filtered-config-list`.
  3. Calls `path-filtering/generate-config` to merge the listed YAML fragments into `/tmp/generated-config.yml`.
  4. Uses `continuation/continue` to continue with the generated config — **this step must include the `parameters:` argument** so pipeline parameters get passed on.

Important note: `path-filtering/mapping` supports lines in multiple formats (path-only, path + config, path + param + value, path + param + value + config). The orb writes two outputs: a parameters JSON and a filtered list of config paths. The next step must merge these appropriately.

---

## 5. Problems encountered (detailed)

### Problem A — Committing an empty `config_continued.yml`

**Symptom:** Generated YAML became `{}` and the pipeline reported "All workflows have been filtered from this Pipeline." or "No Jobs have been run.". Generated YAML printed as `{}`.

**Cause:** CircleCI reads the file at `config-path` during the setup step. If the file exists and is empty (committed), the orb reads `{}` and considers that a completed generated config.

**Fix:** Do not commit an empty continuation file. Either:

- Add the file to `.gitignore` and generate it at runtime, or
- Generate it in a prior job and persist it to workspace before the orb loads it.

### Problem B — `preprocessor.sh` ran and wrote file, but `path-filtering` couldn't find it

**Symptom:** `path-filtering/filter` complained `no such file or directory` for the generated file.

**Cause:** The setup workflow ordering and use of CircleCI workspace. The orb job ran before the generated file was attached or persisted.

**Fix:** Ensure the generation job runs first and persist the generated file with `persist_to_workspace`. In the orb job, attach workspace _after_ `checkout` (see details below). Example pattern:

```yaml
jobs:
  generate-config:
    steps:
      - checkout
      - run: sh .circleci/preprocessor.sh
      - persist_to_workspace:
          root: .
          paths:
            - .circleci/config_continued.yml

workflows:
  path-filtering-setup:
    jobs:
      - generate-config
      - path-filtering/filter:
          requires: [generate-config]
          pre-steps:
            - checkout
            - attach_workspace: { at: "." }
```

Note: `path-filtering/filter` is an orb-provided job; you cannot modify its internal steps — you can, however, pass `pre-steps` for it to run first.

### Problem C — Checkout / attach_workspace ordering — "Directory is not empty and not a git repository"

**Symptom:** After attaching workspace, a later `checkout` failed with `Directory is not empty and not a git repository` or CircleCI did a second checkout.

**Cause:** Attaching a workspace may populate the working directory with files that are not a Git repo. Running `checkout` after `attach_workspace` results in the conflict. The path-filtering orb may internally perform `checkout` as well.

**Fix Options:**

- Preferred: Run `checkout` first in `pre-steps`, then `attach_workspace` so Git is initialized properly.
- If double `checkout` is an issue, accept it (harmless) or fork the orb to disable internal `checkout` (not recommended).

### Problem D — `requires: [generate-config]` causes tag pushes to be skipped

**Symptom:** Removing `requires` made the pipeline run on tag push; leaving it caused the job to be excluded with "All Workflows have been filtered".

**Cause:** The CircleCI workflow engine excludes jobs that are filtered out (tags/branches). If `generate-config` is filtered out for a tag (because no `tags:` filter is defined), then jobs that `require` it are also excluded. Setup workflows + tag filters are tricky and sometimes flaky.

**Fixes:**

- Add explicit `tags:` filters to `generate-config` so it runs on tags you expect.
- Or avoid `requires` in the setup phase (use pre-steps) so the path-filtering job runs independently.

### Problem E — Mapping produced parameters but they appeared empty in continuation ( `{}` )

**Symptom:** `cat /tmp/pipeline-parameters.json` showed `{"always-continue":true}`, but the continued pipeline's "parameters" field was `{}` and `when: << pipeline.parameters.always-continue >>` used default `false`.

**Cause:** Although `set-parameters` writes `/tmp/pipeline-parameters.json`, the _continuation_ step (`continuation/continue`) **must** receive those parameters explicitly. The orb's default `generate-config` does not automatically inject the parameter JSON into the continuation call — the `continuation/continue` step needs a `parameters:` argument (either JSON or a path to the JSON file).

**Fix:** Pass the parameter file to continuation explicitly:

```yaml
- continuation/continue:
    configuration_path: /tmp/generated-config.yml
    parameters: /tmp/pipeline-parameters.json
```

This was the crucial missing piece; without `parameters:` the continuation runs with `{}`.

### Problem F — Script failing with `/bin/sh: syntax error: unexpected "("` inside mapping script

**Symptom:** The mapping script used `[[ ... ]]`, arrays, and `local` — but the environment used `/bin/sh` and not `bash`.

**Cause:** Two shebangs at the top caused `/bin/sh` to be used. The script uses Bash features.

**Fix:** Use a single Bash shebang and set `set -eo pipefail`:

```bash
#!/usr/bin/env bash
set -eo pipefail
```

Also ensure the job environment has `bash` (Alpine may need `apk add --no-cache bash`).

### Problem G — BusyBox image lacks `git`/`ssh`, and apk

**Symptom:** Checkout commands failed or `git` not found; unable to run `ssh` or `git`.

**Cause:** `busybox:latest` is extremely minimal; it lacks package manager tools.

**Fix:** Use a richer base image:

- `cimg/base:stable` or `cimg/node` (already include Git)
- or `alpine:latest` and run `apk add --no-cache git openssh bash` in the job
- or build a custom Docker image with required tools preinstalled

---

## 6. Root causes and deep analysis (short)

- **Lifecycle order matters.** You must persist generated artifacts to workspace and attach them in the right order.
- **Orb contract is explicit but subtle.** `path-filtering/set-parameters` writes artifacts but does not magically inject them into the continuation: you must pass parameter JSON to `continuation/continue` explicitly.
- **Shell runtime matters.** Bash features require `bash` not `sh`.
- **Setup workflows + filters + requires = combinatorial complexity.** When in doubt, run simpler: run generation in a single job, attach files via workspace, and call continuation with the parameter file.

---

## 7. Fixes and concrete snippets

### A. Correct preprocessor script (robust, safe)

```bash
#!/usr/bin/env bash
set -ex
FILTER_LIST="/tmp/filtered-config-list"
:> "$FILTER_LIST"
# Example static list
printf "%s\n" \
  ".circleci/shared-config.yml" \
  ".circleci/code-config.yml" >> "$FILTER_LIST"
# Or build dynamically
# find src/ -name '*.js' -print | sed 's|^|src/|' >> "$FILTER_LIST"
cat "$FILTER_LIST"
```

### B. Ensure Bash is used and tools installed

Prefer `cimg/base:stable` or add to job steps:

```yaml
- run:
    name: Install tools (alpine example)
    command: |
      apk add --no-cache git openssh bash curl jq
```

### C. Generate and persist config before path-filtering runs

```yaml
jobs:
  generate-config:
    docker:
      - image: cimg/base:stable
    steps:
      - checkout
      - run: sh .circleci/preprocessor.sh
      - persist_to_workspace:
          root: .
          paths:
            - .circleci/config_continued.yml
```

In the workflow, require it and attach the workspace in the filter job `pre-steps`.

### D. Pass parameters to continuation/continue

This is the critical fix:

```yaml
- continuation/continue:
    configuration_path: /tmp/generated-config.yml
    parameters: /tmp/pipeline-parameters.json
```

You can also inline JSON:

```yaml
- continuation/continue:
    configuration_path: /tmp/generated-config.yml
    parameters: '{"always-continue":true}'
```

### E. Merge parameters into generated YAML (optional, robust)

If you want the parameter keys to appear inside the generated YAML (so `workflows` with `when:` have those keys defined), merge like this:

```bash
# assume /tmp/filtered-config-list lists YAML files
CONFIG_FILES=$(tr '\n' ' ' < /tmp/filtered-config-list)
# merge fragments
yq eval-all 'explode(.) | . as $item ireduce ({}; . * $item )' $CONFIG_FILES > /tmp/merged-config.yml
# convert params JSON into YAML under top-level 'parameters:'
if [ -s /tmp/pipeline-parameters.json ]; then
  echo "parameters:" > /tmp/params.yml
  yq eval -P '.' /tmp/pipeline-parameters.json | sed 's/^/  /' >> /tmp/params.yml
  yq eval-all 'explode(.) | . as $item ireduce ({}; . * $item )' /tmp/merged-config.yml /tmp/params.yml > /tmp/generated-config.yml
else
  cp /tmp/merged-config.yml /tmp/generated-config.yml
fi
```

This ensures mapping values override defaults in fragments.

---

## 8. Validation & debug techniques

- Always `cat /tmp/pipeline-parameters.json` and `cat /tmp/filtered-config-list` after `set-parameters`.
- Validate generated YAML with `circleci config validate /tmp/generated-config.yml`.
- Use debug job in generated config to `printenv` and check `CIRCLE_TAG`, `CIRCLE_BRANCH`, `CIRCLE_PIPELINE_SOURCE`.
- Check GitHub webhook deliveries and CircleCI pipeline list to ensure push event reached CircleCI.

---

## 9. Impact of the solutions

- Passing `/tmp/pipeline-parameters.json` to `continuation/continue` fixed the issue where `when: << pipeline.parameters.* >>` always read default values. After the fix, dynamic gating works correctly.
- Proper `persist_to_workspace` + `attach_workspace` ordering prevents missing-file errors and the empty generated YAML `{}` problem.
- Switching from BusyBox to `cimg/base` or `alpine` with `apk add` fixed missing `git` and `ssh` tools.
- Fixing bash shebang removed the unexpected `(` syntax errors.

Overall the pipeline became predictable and robust for both branch and tag triggering (once correct tag filters were set).

---

## 10. Recommendations & best practices

- **Do not commit empty continuation files.** Generate them at runtime.
- **Always persist generated artifacts** with `persist_to_workspace` and `attach_workspace` in dependent jobs.
- **Pass parameters explicitly** to `continuation/continue` when using `path-filtering/set-parameters`.
- **Prefer a stable base image** (e.g., `cimg/base`) over raw BusyBox.
- **Keep mapping lines simple** and avoid spaces in tokens. Use separate mapping lines if you need both boolean and config-file behavior.
- **If you rely heavily on tags**, avoid `setup: true` limitations — either create a separate non-setup tag workflow or ensure all setup jobs have tag filters.

---

## 11. Minimal reproduction steps (quick)

1. Create a repo with `setup: true` top-level config that calls `path-filtering/set-parameters` and `path-filtering/generate-config` and `continuation/continue` without `parameters`.
2. Add a small `shared-config.yml` that uses `when: << pipeline.parameters.myflag >>`.
3. Push a change that should set `myflag` via mapping.
4. Observe `cat /tmp/pipeline-parameters.json` contains the mapping but the continuation shows `{}` for parameters and the `when:` uses default.

Fix by adding `parameters: /tmp/pipeline-parameters.json` to `continuation/continue`.

---

## 12. How I reported the doc/bug to CircleCI

I prepared a short, reproducible report showing the missing `parameters:` usage in the docs and provided the minimal config, logs, and a screenshot. I asked them to update the doc's example or explain the contract more explicitly.

If you want to escalate, provide: `cat /tmp/pipeline-parameters.json`, `cat /tmp/filtered-config-list`, the `config.yml` and `shared-config.yml`, and a screenshot of the continuation pipeline showing `parameters: {}`.

---

## 13. Appendix: Useful commands and snippets

- Show changed files:

  ```sh
  git -c core.quotepath=false diff --name-only "$MERGE_BASE" "$CIRCLE_SHA1"
  ```

- Validate generated config:

  ```sh
  circleci config validate /tmp/generated-config.yml
  ```

- Merge YAML fragments with `yq`:

  ```sh
  yq eval-all 'explode(.) | . as $item ireduce ({}; . * $item )' file1.yml file2.yml > merged.yml
  ```

- Convert JSON params to YAML under `parameters:`

  ```sh
  echo "parameters:" > /tmp/params.yml
  yq eval -P '.' /tmp/pipeline-parameters.json | sed 's/^/  /' >> /tmp/params.yml
  ```

---

If you want, I can:

- Generate a minimal reproducible repo and a GitHub issue/PR payload for the CircleCI docs.
- Produce a trimmed `preprocessor.sh` and a complete example `config.yml` + `shared-config.yml` for direct use.

---

_Authored from a real debugging session. Keep this README in the repo to help future maintainers._
