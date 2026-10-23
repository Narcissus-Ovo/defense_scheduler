# Render product-generated synthetic files read-only in separate Office instances.
$ErrorActionPreference = 'Stop'
$qaRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$qaOutput = Join-Path $qaRoot '.tmp\acceptance-20261016'
$records = @()
$excelApp = $null
$workbook = $null
try {
    $excelApp = New-Object -ComObject Excel.Application
    $excelApp.Visible = $false
    $excelApp.DisplayAlerts = $false
    foreach ($name in @('pre-A', 'long-history')) {
        $inputFile = Join-Path $qaOutput "$name.xlsx"
        $outputFile = Join-Path $qaOutput "$name-excel.pdf"
        $workbook = $excelApp.Workbooks.Open($inputFile, 0, $true)
        $workbook.ExportAsFixedFormat(0, $outputFile)
        $records += @{ input = "$name.xlsx"; output = "$name-excel.pdf"; source_sha256 = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash; version = $excelApp.Version; readOnly = $true; engine = 'Microsoft Excel'; status = 'rendered' }
        $workbook.Close($false)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook)
        $workbook = $null
    }
} catch {
    $records += @{ engine = 'Microsoft Excel'; status = 'error'; error = $_.Exception.Message }
} finally {
    if ($workbook) { $workbook.Close($false) }
    if ($excelApp) { $excelApp.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excelApp) }
}
$wordApp = $null
$document = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    foreach ($name in @('pre-A', 'long-history')) {
        $document = $wordApp.Documents.Open((Join-Path $qaOutput "$name.docx"), $false, $true)
        $document.ExportAsFixedFormat((Join-Path $qaOutput "$name-word.pdf"), 17)
        $records += @{ input = "$name.docx"; output = "$name-word.pdf"; source_sha256 = (Get-FileHash -LiteralPath (Join-Path $qaOutput "$name.docx") -Algorithm SHA256).Hash; version = $wordApp.Version; readOnly = $true; engine = 'Microsoft Word'; status = 'rendered' }
        $document.Close(0)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document)
        $document = $null
    }
} catch {
    $records += @{ engine = 'Microsoft Word'; status = 'error'; error = $_.Exception.Message }
} finally {
    if ($document) { $document.Close(0) }
    if ($wordApp) { $wordApp.Quit(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) }
}
$records | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $qaOutput 'office-render.json') -Encoding UTF8
$records | ForEach-Object { [pscustomobject]$_ } | Format-Table engine,status,output
