#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest tests -q
python src/run_experiments.py
python src/analyze.py
python src/primary_statistics.py
python src/llm_study/run.py --backend mock
(cd paper && python build_manuscript.py)
(cd paper && python audit_numbers.py)
(cd paper && python audit_manuscript.py)
(cd paper && python update_readme.py)
(cd paper && python package_supplement.py)
