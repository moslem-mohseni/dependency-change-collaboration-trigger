param([string]$Python='python', [switch]$SkipPdf)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
function Run-Python([string[]]$Arguments) {
 & $Python @Arguments
 if ($LASTEXITCODE -ne 0) { throw "Python step failed: $Arguments" }
}
Run-Python @('-m','pytest','tests','-q')
Run-Python @('src/run_experiments.py')
Run-Python @('src/analyze.py')
Run-Python @('src/primary_statistics.py')
Run-Python @('src/llm_study/run.py','--backend','mock')
Run-Python @('paper/build_manuscript.py')
Run-Python @('paper/audit_numbers.py')
Run-Python @('paper/audit_manuscript.py')
Run-Python @('paper/update_readme.py')
if (-not $SkipPdf) {
 & "$PSScriptRoot/paper/docx2pdf.ps1" -In "$PSScriptRoot/paper/P2_Dependency_Change_Trigger_for_Second_Agent.docx" -Out "$PSScriptRoot/paper/P2_Dependency_Change_Trigger_for_Second_Agent.pdf"
 if ($LASTEXITCODE -ne 0) { throw 'Word export failed' }
}
Run-Python @('paper/package_supplement.py')
