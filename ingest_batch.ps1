# Proofline AI Benchmark - Unified Ingestion Runner
param(
    [string]$Batch = "all"
)

$python = "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe"
$reviewsDir = "reviews"

Write-Host "======================================================================"
Write-Host "PROOFLINE AI REVIEW BENCHMARK - INGESTION ENGINE"
Write-Host "======================================================================"

$allAttempts = @(
    # Batch 1: batch-7b358964 (Initial Batch: Cases 1, 2, 7 - CODE_ONLY)
    @{ Batch = "batch-7b358964"; Case = 1; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case01.md" },
    @{ Batch = "batch-7b358964"; Case = 1; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case01.md" },
    @{ Batch = "batch-7b358964"; Case = 2; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case02.md" },
    @{ Batch = "batch-7b358964"; Case = 2; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case02.md" },
    @{ Batch = "batch-7b358964"; Case = 7; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case07.md" },
    @{ Batch = "batch-7b358964"; Case = 7; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case07.md" },

    # Batch 2: batch-8e1fac6e (Full 8-Case Extension: Cases 3, 4, 5, 6, 8 - CODE_ONLY)
    @{ Batch = "batch-8e1fac6e"; Case = 3; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case03.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 3; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case03.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 4; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case04.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 4; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case04.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 5; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case05.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 5; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case05.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 6; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case06.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 6; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case06.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 8; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-only"; File = "$reviewsDir\chatgpt_case08.md" },
    @{ Batch = "batch-8e1fac6e"; Case = 8; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-only"; File = "$reviewsDir\claude_case08.md" },

    # Batch 3: batch-8aca4c4d (Deployment Snapshot Ablation: Cases 4, 5, 6 - CODE_AND_SNAPSHOT)
    @{ Batch = "batch-8aca4c4d"; Case = 4; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-and-snapshot"; File = "$reviewsDir\chatgpt_case04_snapshot.md" },
    @{ Batch = "batch-8aca4c4d"; Case = 4; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-and-snapshot"; File = "$reviewsDir\claude_case04_snapshot.md" },
    @{ Batch = "batch-8aca4c4d"; Case = 5; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-and-snapshot"; File = "$reviewsDir\chatgpt_case05_snapshot.md" },
    @{ Batch = "batch-8aca4c4d"; Case = 5; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-and-snapshot"; File = "$reviewsDir\claude_case05_snapshot.md" },
    @{ Batch = "batch-8aca4c4d"; Case = 6; Provider = "chatgpt-web"; Model = "gpt-4o"; Context = "code-and-snapshot"; File = "$reviewsDir\chatgpt_case06_snapshot.md" },
    @{ Batch = "batch-8aca4c4d"; Case = 6; Provider = "claude-web";  Model = "claude-3-5-sonnet"; Context = "code-and-snapshot"; File = "$reviewsDir\claude_case06_snapshot.md" }
)

$targetAttempts = $allAttempts
if ($Batch -ne "all") {
    $targetAttempts = $allAttempts | Where-Object { $_.Batch -eq $Batch }
}

$ingestedCount = 0
$pendingCount = 0
$completedBatches = @{}

foreach ($att in $targetAttempts) {
    $fPath = $att.File
    if (Test-Path $fPath) {
        $content = Get-Content -Path $fPath -Raw
        if ($content.Trim().Length -gt 0) {
            Write-Host "`n[INGESTING] Batch: $($att.Batch) | Case $($att.Case) ($($att.Context)) | $($att.Provider) ($($att.Model))..."
            & $python -m benchmark ingest --batch-id $($att.Batch) --provider $($att.Provider) --case $($att.Case) --context $($att.Context) --file $fPath --model $($att.Model) --force
            if ($LASTEXITCODE -eq 0) {
                $ingestedCount++
                $completedBatches[$att.Batch] = $true
            } else {
                Write-Host "[ERROR] Failed to ingest $fPath" -ForegroundColor Red
            }
        } else {
            Write-Host "[WAITING] $fPath is empty. Please paste review response." -ForegroundColor Yellow
            $pendingCount++
        }
    } else {
        Write-Host "[WAITING] Missing file: $fPath" -ForegroundColor DarkGray
        $pendingCount++
    }
}

Write-Host "`n======================================================================"
Write-Host "INGESTION STATUS: $ingestedCount processed / $pendingCount pending"
Write-Host "======================================================================"

foreach ($bId in $completedBatches.Keys) {
    Write-Host "`n[REPORT] Generating comparative reports for $bId..."
    & $python -m benchmark report --batch-id $bId --format all --output-dir "reports\$bId"
}
