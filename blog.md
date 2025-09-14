# CircleCI Dynamic Config with Path-Filtering: A Real-World Implementation Guide

Dynamic configuration in CircleCI promises to revolutionize how we handle
complex CI/CD workflows, but the path from theory to production-ready
implementation is fraught with undocumented pitfalls. This post chronicles my
journey implementing CircleCI's dynamic configuration using the
`circleci/path-filtering` orb, the critical issues I encountered, and the
hard-won solutions that made it work.

## The Vision: Modular, Intelligent CI

The goal was ambitious but necessary: transform our monolithic CI configuration
into a modular, intelligent system that could:

1. **Modularize configuration** into maintainable YAML fragments assembled at
   runtime
2. **Intelligently detect changes** using path-based mapping to trigger only
   relevant workflows
3. **Generate dynamic parameters** to control pipeline execution
4. **Enable cross-repository triggers** when needed
5. **Eliminate unnecessary CI runs** through precise change detection

The impact would be significant: easier maintenance, fewer merge conflicts,
faster CI runs, and true dynamic control over complex workflows.

## Architecture: How It All Fits Together

### Repository Structure

The foundation is a well-organized repository structure that separates concerns:

```
.circleci/
├── config.yml                      # Setup pipeline (setup: true)
├── code-config.yml                 # Jobs for source code changes
├── docs-config.yml                 # Jobs for documentation changes
├── no-updates.yml                  # Fallback when no changes detected
├── custom-circleci-cli-script.sh   # Custom mapping logic
└── shared/                         # Modular configuration fragments
    ├── @parameters.yml
    ├── @shared.yml
    ├── jobs/
    │   ├── any-change.yml
    │   ├── lint.yml
    │   └── test.yml
    └── workflows/
        └── run-on-any-change.yml
```

### The Flow: Setup to Continuation

The implementation follows a two-stage pipeline pattern:

**Stage 1: Setup Pipeline**

1. Checkout and install CircleCI CLI
2. Pack modular configuration fragments using `circleci config pack`
3. Use `path-filtering/set-parameters` to map file changes to parameters
4. Generate consolidated configuration with `path-filtering/generate-config`
5. **Critical**: Continue with both configuration AND parameters

**Stage 2: Continuation Pipeline**

1. Receive merged configuration and mapped parameters
2. Execute workflows conditionally based on `<< pipeline.parameters.* >>` values
3. Optionally trigger additional pipelines via CircleCI API

## Key Design Decisions

### Alpine Base Images for Performance

We chose Alpine Linux base images (~30MB) over standard images (~189MB) to
dramatically reduce cold-start times. The tradeoff required installing necessary
tools:

```bash
apk add --no-cache sudo curl wget git bash jq
```

### Runtime Assembly Over Committed Configs

Rather than committing large, monolithic configuration files, we commit small
fragments and assemble them at runtime. This approach reduces merge conflicts
and enables quicker iteration cycles.

### Explicit Parameter Passing

The most critical design decision was recognizing that parameters must be
explicitly passed to the continuation pipeline - they don't transfer
automatically.

## The Problems: Where Theory Met Reality

### Problem 1: The Vanishing Parameters Mystery

**Symptoms**: Parameters file contained `{"always-continue": true}`, filtered
config list showed correct files, but the continuation pipeline received `{}`
and `when` conditions fell back to defaults.

**Root Cause**: The `continuation/continue` call lacked the `parameters:` field,
causing the continuation pipeline to receive no parameters.

**Solution**:

```yaml
- continuation/continue:
    configuration_path: /tmp/generated-config.yml
    parameters: /tmp/pipeline-parameters.json # This line is CRITICAL
```

**Impact**: This single line enabled true parameterized dynamic pipelines -
previously impossible with standard documentation examples.

### Problem 2: Tag Builds Mysteriously Skipped

**Symptoms**: Pipelines ran fine on branch pushes but were skipped entirely on
tag pushes with "All workflows filtered" message.

**Root Cause**: The `generate-config` workflow lacked tag filters, causing
required jobs to be excluded and dependent workflows to skip.

**Solution**: Ensure dependency workflows have identical filters to dependent
workflows:

```yaml
filters:
  tags:
    only: /.*/
```

### Problem 3: Git Repository Chaos

**Symptoms**: `Directory is not empty and not a git repository` errors and
duplicate checkout operations.

**Root Cause**: Workspace attachment conflicts with checkout operations -
different orbs and steps performing checkout in conflicting ways.

**Solution**: Use `workspace_path: .` parameter to properly coordinate workspace
attachment with checkout, or carefully order `checkout` as a pre-step before
`attach_workspace`.

### Problem 4: Shell Script Compatibility Nightmare

**Symptoms**: `/bin/sh: syntax error: unexpected "("` when scripts used
bash-specific features.

**Root Cause**: Scripts used bash features (`[[ ]]`, arrays, `local`) but
executed under `/bin/sh`.

**Solution**: Always use proper bash shebang:

```bash
#!/usr/bin/env bash
set -eo pipefail
```

This issue was so problematic that I ultimately forked the
`path-filtering/set-parameters` source code into a custom script to ensure bash
compatibility.

### Problem 5: Alpine's Minimalist Reality

**Symptoms**: Missing essential tools like `git`, `bash`, `curl`, `jq` breaking
orb functionality.

**Solution**: Either install required packages or use CircleCI convenience
images like `cimg/base` which include necessary tools pre-installed.

## Critical Implementation Details

### The Mapping Configuration

```yaml
- path-filtering/filter:
    config-path: .circleci/config_continued.yml
    mapping: |
      .* always-continue true .circleci/shared-config.yml
      src/.* build-code true .circleci/code-config.yml
      docs/.* build-docs true .circleci/docs-config.yml
```

### Cross-Repository Pipeline Triggers

For triggering pipelines across repositories or branches, personal API tokens
are required:

```bash
curl -X POST "https://circleci.com/api/v2/project/gh/<org>/<repo>/pipeline" \
  -H "Circle-Token: $PERSONAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "branch": "target-branch",
        "parameters": { "run_post_pipeline": true }
      }'
```

Note: Use `gh` (not `github`) in API URLs, and permission errors often indicate
incorrect token type or repository access issues.

## Debugging Arsenal

When things go wrong (and they will), these commands prove invaluable:

```bash
# Inspect mapping results
cat /tmp/pipeline-parameters.json
cat /tmp/filtered-config-list

# Validate generated configuration
cat /tmp/generated-config.yml
circleci config validate /tmp/generated-config.yml

# Check file changes
git diff --name-only "$(git merge-base origin/main $CIRCLE_SHA1)" "$CIRCLE_SHA1"

# Environment inspection
printenv | sort
```

## Best Practices: Hard-Won Wisdom

1. **Always pass parameters explicitly** to `continuation/continue` when using
   jobs directly rather than orb workflows
2. **Match filters exactly** between dependency and dependent workflows
3. **Use bash for complex scripts** with proper shebang and error handling
4. **Persist artifacts correctly** using workspace paths that make sense for
   your structure
5. **Validate configurations locally** before pushing to catch syntax errors
   early
6. **Use prebuilt images** or create custom images with required tools installed

## The Payoff: Measurable Benefits

After implementing these fixes, the benefits became immediately apparent:

- **Modular maintenance**: Configuration changes now affect only relevant files,
  reducing merge conflicts
- **Faster CI runs**: Path-filtering eliminates unnecessary job execution, and
  Alpine images reduce cold-start times
- **Dynamic control**: True parameterized pipelines enable sophisticated
  workflow logic
- **Cross-repository coordination**: API triggers enable complex deployment
  orchestration
- **Deterministic builds**: Precise change detection ensures predictable CI
  behavior

## Limitations and Gotchas

Dynamic configuration isn't without constraints:

- `setup: true` pipelines have single-use continuation keys - you cannot spawn
  another continuation from within a continued run without creating a new
  pipeline via API
- Project API tokens are limited for v2 endpoints - use personal or service
  account tokens for pipeline triggers
- Mapping lines split on whitespace - avoid spaces in patterns or quote them
  properly
- Different workflows run in separate containers - artifacts must be persisted
  and attached correctly

## The Path Forward

CircleCI's dynamic configuration with path-filtering is powerful but requires
careful implementation to avoid documented pitfalls. The combination of modular
configuration, intelligent change detection, and proper parameter passing
creates a CI system that's both maintainable and efficient.

The key lesson: the official documentation provides the foundation, but
production implementation requires understanding the subtle interactions between
workflows, workspaces, and continuation pipelines. With the fixes documented
here, you can avoid the weeks of debugging I experienced and build robust,
dynamic CI pipelines from the start.

For teams considering this approach, the investment in setup complexity pays
dividends in maintenance simplicity and execution efficiency. Just remember:
always pass those parameters to continuation, match your filters exactly, and
when in doubt, check what's actually in those `/tmp/` files.
