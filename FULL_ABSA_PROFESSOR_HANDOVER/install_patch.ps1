$ErrorActionPreference = "Stop"

$handover = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $handover
$patchRoot = Join-Path $handover "repository_patch"

$requiredExisting = @(
    (Join-Path $repoRoot "data\frozen_research_sample\features.parquet"),
    (Join-Path $repoRoot "data\frozen_research_sample\reviews.parquet"),
    (Join-Path $repoRoot "data\frozen_research_sample\embeddings.npz"),
    (Join-Path $repoRoot "data\frozen_research_sample\SHA256_MANIFEST.csv"),
    (Join-Path $repoRoot "outputs\frozen_research_run\full_dossiers"),
    (Join-Path $repoRoot "src\truststay_evidence\dossier_builder.py"),
    (Join-Path $repoRoot "requirements.txt")
)

$missing = @($requiredExisting | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    Write-Error ("Required existing TrustStay files are missing:`n- " + ($missing -join "`n- "))
    exit 2
}

$copies = @(
    @("scripts\run_full_absa_refresh.py", "scripts\run_full_absa_refresh.py"),
    @("src\truststay_evidence\full_absa_adapter.py", "src\truststay_evidence\full_absa_adapter.py"),
    @("configs\full_absa_aspects.yaml", "configs\full_absa_aspects.yaml"),
    @("requirements_full_absa.txt", "requirements_full_absa.txt"),
    @("FULL_ABSA_RERUN_README.md", "FULL_ABSA_RERUN_README.md"),
    @("FULL_ABSA_VALIDATION.md", "FULL_ABSA_VALIDATION.md"),
    @("tests\test_full_absa_adapter.py", "tests\test_full_absa_adapter.py")
)

foreach ($copy in $copies) {
    $source = Join-Path $patchRoot $copy[0]
    $destination = Join-Path $repoRoot $copy[1]
    $destinationDirectory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
    Write-Host ("Installed " + $copy[1])
}

Write-Host "Patch installed. Run the Windows GPU smoke test from the repository root."
