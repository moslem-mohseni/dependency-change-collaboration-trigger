# Dependency Change Signals and Second Agent Auditing in a Controlled Scheduling Simulation

[![Reproduce research artifact](https://github.com/moslem-mohseni/dependency-change-collaboration-trigger/actions/workflows/reproduce.yml/badge.svg)](https://github.com/moslem-mohseni/dependency-change-collaboration-trigger/actions/workflows/reproduce.yml)

**Parametric simulation research artifact. No real-model Study 2 was run.** Mock results are labelled and excluded from scientific estimates. The confirmed three-author metadata is in paper/author.json and CITATION.cff.

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

## Authors and manuscript

Sepide Ebrahimian Maqsoud, Moslem Mohseni Khah, Navid Sadeghi. Corresponding author: Moslem Mohseni Khah (moslem.mohsenikhah@iau.ir). Affiliations and supplied contact details are centralized in [paper/author.json](paper/author.json). ORCID identifiers were not supplied and are omitted.

The manuscript is prepared for editorial consideration; no journal acceptance or publication is claimed. The repository contains its source and reproducible results. Formal reuse licensing remains as documented in docs/LICENSE_STATUS.md.

## Submission manuscript files

[Word manuscript](manuscript/P2_Dependency_Change_Trigger_for_Second_Agent.docx) · [PDF manuscript](manuscript/P2_Dependency_Change_Trigger_for_Second_Agent.pdf) · [Reproducible supplement](manuscript/supplementary_p2.zip)

These are author-prepared submission files, subject to editorial review. No acceptance or publication status is implied.
