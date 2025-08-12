# Parallax Provider Tutorial — CircleCI Implementation & Post-mortem

Practical notes, decisions, gotchas and fixes for a modular / dynamic CircleCI pipeline used in this repo.
This README documents what I built, problems I hit, how I solved them, and the impact — so you can reproduce, learn, and avoid the same traps.

---

## Quick summary

- Modularized CircleCI using dynamic configuration (`setup: true`) + `circleci/path-filtering` (forked) and `continuation`.
- Pack fragments at runtime (via `circleci config pack` / `preprocessor.sh`) instead of keeping a monolithic `.circleci/config.yml`.
- Use lightweight `alpine` images (with required tools installed) to speed up CI jobs.
- Forked/rewrote `path-filtering/set-parameters` into a bash-friendly script that emits `/tmp/pipeline-parameters.json` and `/tmp/filtered-config-list`.
- Fixed parameter propagation to continuation by explicitly passing the params file to `continuation/continue`.
- Implemented API-based pipeline triggering to start pipelines in the same or other branches/projects (using a Personal API Token or a service-account pattern).

---

# What this repo now does (high level)

1. Packs/merges YAML fragments into a dynamic continuation config at runtime.
2. Detects file changes using a path → mapping table.
3. Produces a parameters JSON and a list of config files from the matched mappings to generate config file for child pipeline.
4. Continues the pipeline with the generated config and the mapped parameters.
5. Optionally triggers another pipeline (same repo / other branch / other repo / other ci vendor ) via CircleCI API.

---

# Directory (recommended)

```
.circleci/
├── config.yml                # setup: true — initial bootstrap
├── config_api.yml            # triggers API calls (optional)
├── config_post.yml           # generated / chosen continuation config
├── preprocessor.sh           # packs fragments (circleci config pack / cat)
├── shared/                   # modular fragments (jobs / workflows)
│   ├── jobs/
│   └── workflows/
└── scripts/
    └── custom-path-filter.sh  # forked path-filtering set-parameters (bash)
```

---

# Key design choices & why

- **Modular fragments**: easier maintenance, smaller diffs, reusable jobs.
- **Pack at runtime**: commit fragments, assemble only when needed (fewer merge conflicts; quicker iteration).
- **Alpine base images**: \~30MB vs \~189MB for larger base images — faster downloads for cold starts (install `bash`, `git`, `curl`, `jq`, `wget`).
- **Explicit parameter passing**: `continuation/continue` must be given `parameters: /tmp/pipeline-parameters.json` — otherwise continuation receives `{}` and `when: << pipeline.parameters.* >>` falls back to defaults.
- **Personal access tokens**: personal API token for cross-repo/branch triggers because those tokens support v2 api version for pipeline triggering.

---

# Important snippets (copy/paste)

**Ensure bash shebang in scripts**

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
    pre-steps:
      - checkout
      - attach_workspace:
          at: .
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

**Merge YAML fragments and apply parameters last (example using `yq`)**

```bash
# merge fragments listed in /tmp/filtered-config-list
CONFIG_FILES=$(xargs < /tmp/filtered-config-list)
yq eval-all 'explode(.) | . as $item ireduce ({}; . * $item )' $CONFIG_FILES > /tmp/merged-config.yml

# convert params json -> params.yml
echo "parameters:" > /tmp/params.yml
yq eval -P '.' /tmp/pipeline-parameters.json | sed 's/^/  /' >> /tmp/params.yml

# merge with params last (params override defaults)
yq eval-all 'explode(.) | . as $item ireduce ({}; . * $item )' /tmp/merged-config.yml /tmp/params.yml > /tmp/generated-config.yml
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

# Problems I faced (detailed) + fixes

### 1. Empty/committed continuation file

**Symptom:** `.circleci/config_continued.yml` committed empty → pipeline immediately produced `{}`.
**Fix:** Don’t commit empty continuation files. Generate them at runtime and persist them to workspace so path-filtering consumes the generated file.

### 2. Workspace/checkout ordering errors

**Symptom:** `Directory not empty and not a git repository` or doubled checkout.
**Fix:** Run `checkout` first in pre-steps, then `attach_workspace`. Example shown above. Accept double checkout logs if orb also checks out.

### 3. Busybox image missing tools

**Symptom:** `git`, `bash`, `curl` missing.
**Fix:** Use `alpine` + `apk add --no-cache git openssh bash curl jq` or `cimg/base:stable`. Or build a custom image with tools preinstalled.

### 4. `requires: [generate-config]` silently skip on tags

**Symptom:** Job dependencies caused pipeline to be skipped on tag pushes.
**Cause:** If a required job is filtered out (no tag filter), dependent jobs are excluded.
**Fix:** Either give `generate-config` explicit tag filters or avoid `requires` in the setup workflow and instead use pre-steps.

### 5. Mapping generated parameters but `parameters` in continuation was `{}`

**Symptom:** `/tmp/pipeline-parameters.json` contained `{"always-continue":true}` but the continued pipeline showed `{}`.
**Fix:** Pass the generated params into `continuation/continue` via `parameters: /tmp/pipeline-parameters.json` OR merge the params into the final generated YAML (as shown above). I raised the docs issue for this behavior (CircleCI docs fix).

### 6. Script failures (unexpected `(`)

**Symptom:** Scripts used bash features but had `#!/bin/sh`.
**Fix:** Use `#!/usr/bin/env bash` + `set -eo pipefail`.

### 7. API branching & permissions gotchas

- **Use a Personal API Token (service account recommended)** for cross-repo/branch triggers.
- Validate slug with GET before POST:

  ```bash
  curl -H "Circle-Token: $TOKEN" https://circleci.com/api/v2/project/gh/<org>/<repo>
  ```

- Ensure the branch exists in CircleCI (push at least once) or use strategy that checks out the target branch dynamically.

---

# Debug checklist (quick)

- `cat /tmp/pipeline-parameters.json` — confirm mapping output.
- `cat /tmp/filtered-config-list` — confirm merge list.
- `cat .circleci/config_continued.yml` after generator.
- `circleci config validate /tmp/generated-config.yml`
- If API call returns `Permission denied`, confirm token type and repo access.
- Use `curl GET` on the project slug to confirm token+slug.

---

# Security note

- **Do not store personal tokens in plaintext or commit them.** Use CircleCI project environment variables or contexts.
- For automation across projects, create a dedicated GitHub service account, add it to repos, then create a personal token for that account and store it in CI env vars.

---

# Major benefits / impact

- Modular configs → easier maintenance & fewer merge conflicts.
- Full dynamic control: you can map files → parameters → control any number of workflows/jobs.
- Lighter/deterministic CI runs: use Alpine images to cut cold-start download times.
- Able to trigger pipelines across branches & projects when needed (with proper token setup).
- The continuation-params fix enables true parameterized dynamic pipelines (previously impossible with the example in the docs).

---

# Known limitations & tips

- `setup: true` pipelines have special behavior — continuation keys are single-use; you cannot spawn another continuation from inside a continued run without making a new pipeline (via API).
- Project API tokens are limited for v2 endpoints; use personal/service tokens for `/api/v2/pipeline`.
- Mapping lines split on whitespace — avoid spaces in filenames/patterns or quote/escape them.

---

If you want, I can:

- produce a minimal reproducible example repo (configs + preprocessor) and a script to validate locally via `circleci local execute`,
- add the small text flow diagram for README,
- or convert parts of this README into smaller CONTRIBUTING.md sections for maintainers.

Would you like the minimal repro next?
