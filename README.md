# CircleCI: Dynamic config with path-filtering — notes, problems, fixes, and lessons

This README documents my real-world implementation of CircleCI dynamic configuration using the `circleci/path-filtering` orb, the issues I ran into, how I solved them, and the impact of those fixes. It’s written as a reproducible guide and post-mortem so you (or CircleCI docs maintainers) can avoid the same traps.

---

# What this repo now does (high level)

1. Modularize CI config into multiple YAML fragments (`.circleci/jobs/*.yml`, `workflows/*.yml`) and assemble them at runtime thus keeping them small, simple and maintanable.
2. Detects file changes using a path → mapping table.
3. Produces a parameters JSON and a list of config files from the matched mappings to generate config file for child pipeline.
4. Continues the pipeline with the generated config and the mapped parameters.
5. Optionally triggers another pipeline (same repo / other branch / other repo / other ci vendor ) via CircleCI API.
   6 Avoid running full pipelines on irrelevant changes by using path-filtering orb mappings.
   7 Use `pipeline.parameters` (booleans) to gate `when: << pipeline.parameters.some_flag >>` logic in the generated continuation config.

# Major benefits / impact

- Modular configs → easier maintenance & fewer merge conflicts.
- Full dynamic control: you can map files changes to parameters to control any number of workflows/jobs.
- Lighter/deterministic CI runs: use Alpine images to cut cold-start download times.
- Able to trigger pipelines across branches & projects when needed (with proper token setup).
- The continuation-params fix enables true parameterized dynamic pipelines (previously impossible with the example in the docs).

---

# Key design choices & why

- **Modular fragments**: easier maintenance, smaller diffs, reusable jobs.
- **Pack at runtime**: commit fragments, assemble only when needed (fewer merge conflicts; quicker iteration).
- **Alpine base images**: \~30MB vs \~189MB for larger base images — faster downloads for cold starts (install `bash`, `git`, `curl`, `jq`, `wget`).
- **Explicit parameter passing**: `continuation/continue` must be given `parameters: /tmp/pipeline-parameters.json` — otherwise continuation receives `{}` and `when: << pipeline.parameters.* >>` falls back to defaults.
- **Personal access tokens**: personal API token for cross-repo/branch triggers because those tokens support v2 api version for pipeline triggering.

---

## Repo layout (recommended)

```
.
- .circleci
  - code-config.yml                 #  job pipeline for when src/.* changes
  - config.yml                      #  setup: true (setup pipeline)
  - custom-circleci-cli-script.sh   #  custom script to map  files changes to relevant config yml files build list to generate final config
  - docs-config.yml                 #  job pipeline for when src/.* changes
  - no-updates.yml
  - shared                          #  directory to pack (.circleci/shared-config.yml)
    - @paramters.yml                #  store the parameters
    - @shared.yml                   #  contains the version
    - jobs                          #  jobs divided into multiple files, circleci config pack consider folder name as job name
      - any-change.yml
      - lint.yml
      - test.yml
    - workflows
      - run-on-any-change.yml
- docs
  - my-docs.txt
- src
  - my-code.txt
```

## Correct high-level flow

1. **Setup job runs (setup: true)**

   - `checkout`
   - run `circleci-cli/install`
   - run circleci config pack .circleci/shared >> .circleci/shared-config.yml — generate `.circleci/config_continued.yml`
   - `path-filtering/set-parameters` (mapping) → produces:

     - `/tmp/pipeline-parameters.json` (or `$OUTPUT_PATH`)
     - `/tmp/filtered-config-list` (list of config files to include in generated-config.yml file)

   - `path-filtering/generate-config` → merges files in `/tmp/filtered-config-list` to `/tmp/generated-config.yml`
   - **CRITICAL**: call `continuation/continue` with both:

     ```yaml
     configuration_path: /tmp/generated-config.yml
     parameters: /tmp/pipeline-parameters.json
     ```

     This passes the mapping-produced parameters into the continued pipeline.

2. **Continuation pipeline runs**

   - It receives the merged config and the `parameters` JSON. Conditional job execution like:

     ```yaml
     parameters:
       always-continue:
         type: boolean
         default: false

     when: << pipeline.parameters.always-continue >>
     ```

     will now reflect the mapped booleans.

---

# Important snippets

**Ensure bash shebang in scripts to run bash related functions and exit safely with the correct error output**

```bash
#!/usr/bin/env bash
set -eo pipefail
# ...script content using arrays, [[ ]] etc...
```

**Persist generated config so path-filtering can see it**

```yaml
jobs:
  generate-config:
    docker:
      - image: cimg/base:stable
    steps:
      - checkout
      - run: .circleci/preprocessor.sh # writes .circleci/config_continued.yml
      - persist_to_workspace:
          root: .
          paths:
            - .circleci/config_continued.yml
```

**Path-filtering pre-steps so workspace is attached safely**

```yaml
- path-filtering/filter:
    requires: [generate-config]
    checkout: true #(default)
    workspace_path: . #(root folder to access shared-config.yml file at run time)
    config-path: .circleci/config_continued.yml
    mapping: |
      .* always-continue true .circleci/shared-config.yml
      src/.* build-code true .circleci/code-config.yml
```

**CRITICAL: pass params to continuation**

```yaml
- continuation/continue:
    configuration_path: /tmp/generated-config.yml
    parameters: /tmp/pipeline-parameters.json
```

**Trigger another pipeline via API (use Personal API Token or service-account token)**

```bash
curl -X POST "https://circleci.com/api/v2/project/gh/<org>/<repo>/pipeline" \
  -H "Circle-Token: $PERSONAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "branch": "alpine-branch",
        "parameters": { "run_post_pipeline": true }
      }'
```

- use `gh` (not `github`) in the API URL.
- `Permission denied` often means token type or repo access is incorrect.

---

## Real problems I encountered & how I solved them

### 1) **Mapping wrote params but continuation saw `{}`**

- Symptom: `/tmp/pipeline-parameters.json` contained `{"always-continue": true}`, `/tmp/filtered-config-list` listed `.circleci/shared-config.yml`, but continued pipeline's `"parameters": {}` and `when` conditions fell back to defaults.
- Root cause: `continuation/continue` was called without `parameters:` set, so the continuation pipeline got no parameters and resorted to its defautl '{}'.
- Fix: Add `parameters: /tmp/pipeline-parameters.json` to the `continuation/continue` call.
- Impact: `<< pipeline.parameters.always-continue >>` now reflects the mapped value.

### 2) **Using `generate-config` with tag filters made the workflow skip on tag pushes**

- Symptom: Pipeline ran when I added tag filters, but without tag filters present it was skipped with "All workflows filtered".
- Root cause: `generate-config` workflow didn't had tags filter which caused `generate-config` job to never run , so a required job was excluded and dependent job skipped which resulted entire workflow skip.
- Fix:

  - Ensure `generate-config` is allowed on tags too (set tags filter)

- Impact: Made tag-triggered builds stable.

### 3) **Detached HEAD / checkout errors when using workspace**

- Symptom: `Directory ... is not empty and not a git repository` or duplicate `checkout`.
- Root cause: using `attach_workspace` in prestep without checkout restores files into working dir; running `checkout` at runtime afterwards causes conflicts or using `attach_workspace` along with `checkout` in prestep causes checkout to run twice in prestep and run time.
- Fix:

  - Preferred: put the parameters `workspace_path: .` which attaches workspace and checkout happen normally during runtime
  - If using orb `path-filtering/filter` which internally performs checkout, put `checkout` as pre-step before `attach_workspace` (it avoids the "not a git repo" error). Accept that orb may also run an internal checkout — double checkout is slower but stable. or set `checkout:false` in parameters to disable running it in runtime again.

- Impact: Avoids git errors and race conditions.

### 4) **Shebang / shell incompatibility**

- Symptom: `/bin/sh: syntax error: unexpected "("`
- Root cause: Script used bash features (`[[ ]]`, arrays, `local`) but ran under `/bin/sh`.
- Fix: Ensure script starts with:

  ```bash
  #!/usr/bin/env bash
  set -eo pipefail
  ```

  and remove `#!/bin/sh` first line.

- Impact: Script runs reliably in CircleCI.
  due to incompatibility of shell the path-filtering/set-parameters could not run on `/bin/sh` so forked the source of `path-filtering/set-parameters` in to `custom-circleci-cli-script.sh` and exported required parameters inside the script and ran the script using bash shell which correctly produces the same output as path-filtering/set-paramters job `/tmp/pipeline-parameters.json` , `/tmp/filtered-config-list`

### 5) **Alpine image limitations**

- Symptom: `git` `sudo` `bash` `curl` `wget` `jq` missing, unable to use circleci orbs and cli tools and bash script .
- Fix: `apk add --no-cache sudo curl wget git bash curl jq` , or use CircleCI convenience images like `cimg/base` / `cimg/node`. Alternatively build a custom Docker image with tools preinstalled.
- Impact: Faster, more robust CI runs; using alpine docker image , or more convenience using circle ci base images.

---

## Debugging checklist / commands

Run these from CI job steps to inspect state:

```sh
# show mapping output and filtered list
cat /tmp/pipeline-parameters.json
cat /tmp/filtered-config-list

# show generated config
cat /tmp/generated-config.yml

# show env
printenv | sort

# show changed files compared to merge base
git -c core.quotepath=false diff --name-only "$(git merge-base origin/main $CIRCLE_SHA1)" "$CIRCLE_SHA1"

# verify branch contains a commit
git branch --contains <commit-sha>

# validate CircleCI generated config locally (if CLI installed)
circleci config validate /tmp/generated-config.yml
```

Also check GitHub → Settings → Webhooks → Recent Deliveries for tag push webhook status.

---

- Suggested doc fix: in the “Pack, generate, validate” how-to example, add the `parameters:` line to the `continuation/continue` example:

  ```yaml
  - continuation/continue:
      configuration_path: /tmp/generated-config.yml
      parameters: /tmp/pipeline-parameters.json
  ```

I prepared wording for a support ticket; include the above plus a short reproduction.

---

## Root causes and deep analysis (short)

- **different workflows run in separate containers** You must persist generated artifacts to workspace and attach them in the right order to access artifacts.
- **when using orbs jobs directly rather than orb workflow pass the parameters explicitly for each orb job** `path-filtering/set-parameters` writes artifacts but does not magically inject them into the continuation: you must pass parameter JSON to `continuation/continue` explicitly.
- **Shell runtime matters.** Bash features require `bash` not `sh`.
- **dependency workflow must have the same filters as dependent workflow** filters and conditions are process in the compile time so if the filters are not present in the dependency workflow the workflow won't run

## Best practices & gotchas (summary)

- **Always** pass the generated parameters into `continuation/continue` when using it as a job and not in a workflow of a particular orb.
- If you list a config-path in mapping lines, ensure the included config declares corresponding `parameters:` (or merge params into final YAML as a separate step).
- Avoid `requires:` in setup workflows unless you are certain the required job runs for every trigger (branch or tag). For tags, explicitly allow tags in filters OR combine steps in one job.
- if the dependent job has a filter (branch or tag) then the required job must also have the same filter
- Use Bash for mapping scripts; ensure `#!/usr/bin/env bash` + `set -eo pipefail`.
- Use `/tmp` (root path) vs `.` (repo root) appropriately when persisting/attaching workspace.
- Prefer prebuilt Docker images with required tools, or build your own image.

---

## Example troubleshooting flow I used

1. `cat /tmp/pipeline-parameters.json` — confirmed mapping wrote booleans.
2. `cat /tmp/filtered-config-list` — confirmed which config(s) were selected.
3. `cat /tmp/generated-config.yml` — discovered `parameters:` absent or defaults present.
4. Realized `continuation/continue` was not given `parameters:` → added `parameters: /tmp/pipeline-parameters.json`.

# Known limitations & tips

- `setup: true` pipelines have special behavior — continuation keys are single-use; you cannot spawn another continuation from inside a continued run without making a new pipeline (via API).
- Project API tokens are limited for v2 endpoints; use personal/service tokens for `/api/v2/pipeline`.
- Mapping lines split on whitespace — avoid spaces in filenames/patterns or quote/escape them.

---

## Appendix — issue ticket : https://github.com/circleci/circleci-docs/issues/9480

---

Here’s a condensed **summary of the key points** from the GitHub issue README:

**Key Points Summary**

1. **Problem Location**

   - Found in the CircleCI official guide: _Using Dynamic Configuration → Setup_ (section “Pack, generate, and validate a configuration file for pipeline continuation”).

   - The _"Using Dynamic Configuration"_ guide was missing parameters in the continuation/continue job.
   - This bug prevented full flexibility in passing parameters to dynamically generated pipelines.

2. **Root Cause**

- the parameters inside the mapping are currently irrelevant as they are never being utilized by the `continuation/continue` orb.
- This is required because we are **not** using `path-filtering/filter` (workflow-level),
  but instead using separate jobs:

  - `path-filtering/set-parameters`
  - `path-filtering/generate-config`
  - `continuation/continue`

- each job in this case requires parameters/inputs to passed into them explicitly or the default values of the respective job is considered.
- path-filtering/filter worklow internally passes the parameters into the respective jobs
- The example in the guide omits the `parameters:` field in the `continuation/continue` step.
- This causes the parameters generated by `path-filtering/set-parameters` (saved in `/tmp/pipeline-parameters.json`) to be ignored, and `{}` is passed instead.

3. **Impact of the problem**

   - In the old setup, you could **only control the number of files** used for triggering workflows.
   - Dynamic config `when:` conditions using `<< pipeline.parameters.* >>` always evaluate to their **default values** in the YAML files, not the intended mapped values from `path-filtering`.
   - As a result, even if a file change matches the mapping, the corresponding jobs/configs do not run because parameters inside the mapping were ignored, meaning you couldn’t control workflows using parameters.

4. **Reproduction**

   - Follow the CircleCI guide exactly.
   - Make a change matching the regex mapping.
   - Observe in the CircleCI UI: _Continue pipeline step → Parameters: {}_
   - The expected mapped parameter (e.g., `always-continue: true`) is missing.

5. **Solution**

   - Update the `continuation/continue` step to explicitly pass the parameters file:

     ```yaml
     - continuation/continue:
         configuration_path: /tmp/generated-config.yml
         parameters: /tmp/pipeline-parameters.json
     ```

   - `/tmp/pipeline-parameters.json` is the `<< parameters.output-path >>` defined in `path-filtering/set-parameters`.

6. **Result After Fix**

   - Parameters are successfully passed to the continuation pipeline.
   - Jobs/configs with `when:` conditions now trigger correctly when relevant file changes occur.

7. **Impact of the Fix**

   - Now you can:

     - Pass **any number of parameters**.
     - Pass **any number of files** in the mapping.
     - Dynamically control **any number of files and workflows** in the generated pipeline.

---

## License & credits

This work is my practical implementation notes and bug report. Use freely; attribution appreciated if you copy/modify it.

---
