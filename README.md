# CircleCI: Dynamic config with path-filtering — notes, problems, fixes, and lessons

This README documents my real-world implementation of CircleCI dynamic configuration using the `circleci/path-filtering` orb, the issues I ran into, how I solved them, and the impact of those fixes. It’s written as a reproducible guide and post-mortem so you (or CircleCI docs maintainers) can avoid the same traps.

---

## TL;DR — what I built and why it mattered

I implemented a dynamic-config pipeline that:

- Uses a small **setup** pipeline to decide what to run (based on changed files),
- Packs modular shared-config fragments into a single shared-config.yml file dynamically on run time,
- Passes parameter flags (booleans) detected by path-filtering into the continuation run, so `when: << pipeline.parameters.something >>` works.

Problems I faced (and fixed):

- Mapping parameters were produced but not applied to the continuation — continuation received `{}`.
- Generated-config file naming/typos and workspace attach/checkout ordering caused file-not-found and “not a git repo” errors.
- My mapping script failed under `/bin/sh` because of bash-specific syntax.
- Alpine base image lacked ` git``sudo ` `bash` `jq` `curl` `wget` `ssh` which was required by the orbs

Impact:

- After fixes, mapping booleans are honored in continuation, tag builds trigger correctly, and the flow is stable and reproducible.
- I filed a clear support/bug report and a doc-fix recommendation to CircleCI (see section below).
- MAJOR IMPACT: due to finding and consequently fixing the bug of the missing parameters from the how-to-guide of Using Dynamic Configuration - Now anyone can pass any number of parameters and files in the mapping and control any number of files and workflows in the dynamically generated pipeline which was otherwise impossible in the current setup which only allows for controlling just the numbers of files since the parameters inside the mapping are currently irrelevant as they are never being utilized by the continuation/continue orb as they are not being explicitly passed in the orb which is required since now continuation/continue is being used a separate job rather since we are not using the path-filtering/filter workflow but instead using jobs path-filtering/set-parameters, path-filtering/generate-config and continuation/continue which all require their own parameters

---

## Repo layout (recommended)

```
.
- .circleci
  - code-config.yml
  - config.yml                      #  setup: true (setup pipeline)
  - custom-circleci-cli-script.sh   #  custom script to build list / generate final config
  - docs-config.yml
  - no-updates.yml
  - shared                          #  directory to pack (.circleci/shared-config.yml)
    - @paramters.yml
    - @shared.yml
    - jobs
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

## Real problems I encountered & how I solved them

### 1) **Mapping wrote params but continuation saw `{}`**

- Symptom: `/tmp/pipeline-parameters.json` contained `{"always-continue": true}`, `/tmp/filtered-config-list` listed `.circleci/shared-config.yml`, but continued pipeline's `"parameters": {}` and `when` conditions fell back to defaults.
- Root cause: `continuation/continue` was called without `parameters:` set, so the continuation pipeline got no parameters.
- Fix: Add `parameters: /tmp/pipeline-parameters.json` to the `continuation/continue` call.
- Impact: `<< pipeline.parameters.always-continue >>` now reflects the mapped value.

### 2) **Using `generate-config` with tag filters made the workflow skip on tag pushes**

- Symptom: Pipeline ran when I added tag filters, but without tag filters present it was skipped with "All workflows filtered".
- Root cause: `generate-config` workflow didn't had tags filter which caused `generate-config` job to never run , so a required job was excluded and dependent job skipped.
- Fix:

  - Ensure `generate-config` is allowed on tags too (set tags filter), **or**

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

---

## Appendix — issue ticket : https://github.com/circleci/circleci-docs/issues/9480

---

Here’s a condensed **summary of the key points** from the GitHub issue README:

**Key Points Summary**

1. **Problem Location**

   - Found in the CircleCI official guide: _Using Dynamic Configuration → Setup_ (section “Pack, generate, and validate a configuration file for pipeline continuation”).

2. **Root Cause**

   - The example omits the `parameters:` field in the `continuation/continue` step.
   - This causes the parameters generated by `path-filtering/set-parameters` (saved in `/tmp/pipeline-parameters.json`) to be ignored, and `{}` is passed instead.

3. **Impact**

   - Dynamic config `when:` conditions using `<< pipeline.parameters.* >>` always evaluate to their **default values** in the YAML files, not the intended mapped values from `path-filtering`.
   - As a result, even if a file change matches the mapping, the corresponding jobs/configs do not run.

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

---

## License & credits

This work is my practical implementation notes and bug report. Use freely; attribution appreciated if you copy/modify it.

---
