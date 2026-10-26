# Dependency Change Signals and Second Agent Auditing in a Controlled Scheduling Simulation

**فارسی:** در این شبیه‌سازی، سیگنال ساختاری وابستگی برای تصمیم اقتصادی فراخوانی عامل دوم ضعیف است؛ نتیجه به مدل خطا وابسته است.

## Findings and scope
Default test feasibility is 0.832 for repair and 0.990 after audit. The load trigger calls an audit on 0.9925 of episodes. Its utility difference from rate-matched random invocation is 0.000315, interval [0.000122, 0.000536], Holm p=0.01540: detectable but tiny. Critical-overlap and resource-pressure features are exploratory extensions fixed before the revised run. No equivalence or universal routing impossibility is claimed.

All scientific outcomes come from algorithmic agents with assumed check omissions and token charges. CP-SAT uses a deterministic budget; raw records retain status, incumbent and lower bound. Feasibility is exact; reference-relative makespan is not universally an optimality gap. No external benchmark was run.

## Reproduce
Python 3.12 with pinned requirements (NumPy 2.x is required by OR-Tools):

```bash
pip install -r requirements.txt
bash run_all.sh
docker build -t p2_collaboration_trigger .
docker run --name p2_reproduction p2_collaboration_trigger
docker cp p2_reproduction:/work/results ./container_results
docker cp p2_reproduction:/work/paper/supplementary_p2.zip ./
```

```powershell
./run_all.ps1
./run_all.ps1 -SkipPdf
```

The pipeline runs tests, simulation, analysis, clustered primary comparisons, a labelled model-harness mock, DOCX construction, numeric/citation/template audits and supplementary packaging. Windows PDF export needs Word; Docker creates DOCX without Word. Exact model availability evidence is in results/llm/status.json. No real model was available: no credentials/local runtime, and official runtime acquisition timed out. Mock completions are pipeline tests, never model findings.

## Model protocol
The separate src/llm_study harness has 204 synthetic twelve-task episodes in disjoint development/test streams. LLMClient supports mock, OpenAI, Anthropic, local OpenAI-compatible and Ollama endpoints, hashes/caches prompts and retains raw transcripts. Paid calls fail closed without explicit conservative prices and a persistent USD 5 budget. Install/configure an actual provider, then inspect the client configuration before invoking a paid backend; an API key is never packaged. The mock pipeline is safe to rerun offline.

## Files
- src/: simulator, exact validator, bounded solver, policies, analysis and separate model harness.
- tests/: generator, domain validation, solver-status, feature and cached-client tests.
- results/: raw paired episodes, summaries, primary contrasts, AUC intervals and labelled mock records.
- figures/: analysis plots; paper/: template, central author.json, builder, audits and supplementary ZIP.
- literature/: primary-record ledger and closest-work full-text notes.

Edit paper/author.json and rebuild with `python paper/build_manuscript.py`; from paper/ use `python build_manuscript.py`. Export PDF again after metadata changes. The supplementary ZIP includes a SHA-256 manifest and can run outside this checkout. Generated results use fixed seed streams; running the analysis twice should give identical CSV content. Supplemental price-grid maxima are exploratory and their pointwise intervals do not correct for selection.
