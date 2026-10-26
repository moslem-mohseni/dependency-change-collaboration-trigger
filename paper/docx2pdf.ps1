param([string]$In, [string]$Out)
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$d = $w.Documents.Open($In)
$d.Fields.Update() | Out-Null
$d.ExportAsFixedFormat($Out, 17)
$n = $d.ComputeStatistics(2)
$d.Close($false)
$w.Quit()
Write-Output "pages=$n"
