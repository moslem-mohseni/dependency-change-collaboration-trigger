# Dependency Change Signals and Second Agent Auditing in a Controlled Scheduling Simulation

[![Reproduce research artifact](https://github.com/moslem-mohseni/dependency-change-collaboration-trigger/actions/workflows/reproduce.yml/badge.svg)](https://github.com/moslem-mohseni/dependency-change-collaboration-trigger/actions/workflows/reproduce.yml)

**Parametric simulation research artifact. No real-model Study 2 was run.** Mock results are labelled and excluded from scientific estimates. Author and formal citation metadata are awaiting final confirmation; generated Word/PDF manuscripts are not published here yet.

## Start here
- [Findings, assumptions, seeds and detailed reproduction](docs/RESEARCH.md)
- [Publication scope and maintenance](docs/PUBLICATION.md)
- [Verified references](literature/verified_sources.md) and [closest-work full-text notes](literature/notes_fulltext.md)
- [Citation status](CITATION.md) and [license status](docs/LICENSE_STATUS.md)
- [Scientific results](results/) and [figures](figures/)

## Reproduce the checked-in results
```bash
python -m pip install -r requirements.txt
python scripts/verify_publication.py
python scripts/reproduce.py
```
Use Python 3.12. The final command runs tests, all scientific experiments, analysis, a separate labelled mock protocol, document generation, audits and supplementary packaging. It compares every regenerated CSV exactly with the checked-in baseline and writes artifacts/reproducibility.json. Windows uses the included PowerShell pipeline with PDF export disabled; Linux uses Bash. Docker instructions are in docs/RESEARCH.md.

## Evidence and limits
The local artifact passed 17 tests and exact repeated-host/Docker comparison of 8 scientific CSVs plus a separate mock CSV. GitHub Actions independently checks each pushed commit; its badge is the current remote status. Detailed scientific limitations remain in docs/RESEARCH.md. SOURCE_MANIFEST.json and RESULTS_MANIFEST.json identify the published inputs.

The model protocol, cached provider interface and persistent USD 5 cap are included, but no model/provider performance is claimed. Only synthetic mock traces are under results/llm/mock_transcripts. New live response caches, secrets and local logs are ignored.

## Pending metadata
Final three-author metadata and formal citation/license choices will be completed after confirmation. The template author fixture is not a final author list. No DOI, accepted manuscript or journal publication is claimed. This repository can already be identified by its URL and exact commit.
