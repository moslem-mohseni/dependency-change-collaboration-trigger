# Publication boundary and maintenance

## Published artifact
This checkout publishes P2 sources, tests, synthetic CSV results, figures, verified-source records, reading notes and clearly labelled mock transcripts. The scientific src/ Python files are unchanged from the locally audited artifact, apart from text line-ending normalization by Git. SOURCE_MANIFEST.json records source inputs and RESULTS_MANIFEST.json records the published CSV baseline.

Local pre-publication evidence records 17 passing tests and 8 scientific CSV files exactly reproduced twice and in Docker, with a separate mock CSV. These local receipts are not a claim that a future GitHub run passed. GitHub Actions reports its own outcome for the pushed commit.

## Publication-only adaptations
The README generator writes docs/RESEARCH.md so reproducing the work preserves the repository landing page. Supplementary packaging includes publication documentation/scripts and excludes runtime caches. Numeric auditing recognizes the actual build-date metadata; scientific values still require recomputation. The public author fixture retains name/affiliation/ORCID placeholders and uses the confirmed university correspondence address. Final authorship remains pending. Generated Word/PDF manuscripts are excluded from Git until metadata is finalized.

Original full-text HTML/PDF caches, local paths, host execution logs, credentials, runtime installers and external packages are excluded. Only synthetic mock responses are published; new runtime response caches are ignored by Git.

## Exact reproduction
Install Python 3.12 requirements and run `python scripts/reproduce.py`. It snapshots every checked-in CSV, runs the complete tests/experiments/analysis/manuscript/audits/package pipeline, and uses pandas exact-value comparison for every regenerated CSV. A failure stops the job and retains artifacts/run.log. No real API is called by this command. Generated manuscript date metadata reflects the build; CSVs do not depend on it.

## Updates and push discipline
Use a focused branch, inspect `git diff`, and stage named paths. Never force-push published evidence. If scientific source or results intentionally change, regenerate results and both input manifests, explain the design change, and keep the earlier commit identifiable. Do not relabel mock outcomes as model findings. Pull requests and main-branch pushes both run the complete reproduction check. Action dependencies are pinned to verified immutable commits.

Before a formal release/citation, confirm all author metadata and the project license. Add actual repository references to the manuscript only after choosing the exact version to cite. There is currently no DOI or journal submission claim.
