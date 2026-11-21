<#
.SYNOPSIS
  Run the ASMAE seven-wave candidate qualification on the Windows checkout.
.DESCRIPTION
  Records each real exit code, stdout/stderr log and a JSON receipt.
  Stops on first failed gate. Never promotes branches or certifies physical RF.
#>
param(
  [string] $ExpectedHead = "a12b499d934326e55c7cee037229457254f104e4",
  [string] $OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$actualHead = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualHead -ne $ExpectedHead) {
  throw "Wrong checkout. Expected exact candidate HEAD $ExpectedHead; found $actualHead."
}

if (-not $OutputDirectory) {
  $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
  $OutputDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "akaloris-7wave-$stamp"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$records = New-Object System.Collections.ArrayList
$receiptPath = Join-Path $OutputDirectory "seven_wave_receipt.json"
$script:allPassed = $false

function Run-Gate {
  param([string]$Name, [string]$Exe, [string[]]$Arguments)

  $slug = ($Name -replace "[^a-zA-Z0-9]+", "-").Trim("-").ToLowerInvariant()
  $log = Join-Path $OutputDirectory "$slug.log"
  Write-Host ""
  Write-Host "=== $Name ===" -ForegroundColor Cyan
  Write-Host "$Exe $($Arguments -join ' ')"
  $start = Get-Date
  $priorPreference = $ErrorActionPreference
  try {
    # Native applications can emit harmless stderr even on an exit-0 result.
    $ErrorActionPreference = "Continue"
    & $Exe @Arguments 2>&1 | Tee-Object -FilePath $log | Out-Host
    $exitCode = [int] $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $priorPreference
  }
  $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
  [void] $records.Add([pscustomobject]@{
    gate = $Name
    command = "$Exe $($Arguments -join ' ')"
    exit_code = $exitCode
    elapsed_seconds = $duration
    log_file = $log
  })
  if ($exitCode -ne 0) {
    throw "$Name FAILED (exit $exitCode). See $log"
  }
}

try {
  Run-Gate "sgp4 module import" "python" @("-c", "from sgp4.api import Satrec, jday; print('sgp4 import OK')")
  Run-Gate "MESIA P08 scanner" "python" @("-m", "services.agribrain.mesia.governance.claim_scanner")

  Run-Gate "MESIA full suite" "python" @(
    "-m", "pytest", "services/agribrain/mesia/tests/", "-q"
  )
  Run-Gate "Layer0 full suite" "python" @(
    "-m", "pytest", "services/agribrain/layer0/tests/", "-q"
  )
  Run-Gate "ASMAE Layer05 full suite" "python" @(
    "-m", "pytest", "services/agribrain/layer05_asmae/tests/", "-q"
  )
  Run-Gate "Intermediate scientific layers" "python" @(
    "-m", "pytest",
    "services/agribrain/layer1_fusion/tests/",
    "services/agribrain/layer2_veg_int/tests/",
    "services/agribrain/layer3_decision/tests/",
    "services/agribrain/layer3_water/tests/",
    "services/agribrain/layer4_nutrients/tests/",
    "services/agribrain/layer5_bio/tests/",
    "services/agribrain/layer6_exec/tests/",
    "services/agribrain/layer6_yield/tests/",
    "services/agribrain/layer7_planning/tests/",
    "services/agribrain/layer7_risk/tests/",
    "services/agribrain/layer8_prescriptive/tests/",
    "services/agribrain/layer9_interface/tests/",
    "services/agribrain/layer10_sire/tests/",
    "-q"
  )
  Run-Gate "W1B and W2A service contracts" "python" @(
    "-m", "pytest",
    "services/agribrain/rollout/tests/test_asmae_w1b_learning_eligibility_contract.py",
    "services/agribrain/tests/test_asmae_w2a_physical_semantics.py",
    "services/agribrain/tests/test_w01_w02_water_conservation_and_l4_boundary.py",
    "-q"
  )
  Run-Gate "W1B and P2 frontend authority contracts" "node" @(
    "--test",
    "tests/frontend/asmae-w1b-route-and-map-authority.test.mjs",
    "tests/frontend/asmae-p2-15-p2-16-diagnostic-authority.test.mjs"
  )
  Run-Gate "Prisma client generation" "npx" @("prisma", "generate")
  Run-Gate "Full frontend TAP" "node" @("scripts/run-frontend-tests.mjs")
  Run-Gate "TypeScript" "npx" @("tsc", "--noEmit")
  $script:allPassed = $true
} finally {
  $receipt = [ordered]@{
    candidate_commit = $actualHead
    finished_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    all_passed = $script:allPassed
    gate_count_completed = $records.Count
    gates = @($records)
    physical_receiver_provenance_certified = $false
    one_meter_resolution_certified = $false
    signed_actuation_enabled = $false
    pr32_promotion_authorized = $false
  }
  $receipt | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $receiptPath
  Write-Host "Qualification receipt: $receiptPath"
}
