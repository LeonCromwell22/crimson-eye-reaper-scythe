# Run one scythe stage headless, from an empty scene.
#
# WHY THIS AND NOT THE BRIDGE
#   s0_setup calls read_factory_settings, so running through the live bridge
#   would discard whatever the open Blender session has unsaved. Headless cannot
#   touch a user session, it is reproducible, and every artefact lands in out/.
#
# USAGE
#   powershell -NoProfile -File tools/build_headless.ps1 -Stage s16_export
#   powershell -NoProfile -File tools/build_headless.ps1 -Stage all
#   powershell -NoProfile -File tools/build_headless.ps1 -Stage s0_setup -Snapshots
param(
    [string]$Stage = 's0_setup',
    [string]$Blender = 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe',
    [switch]$Snapshots,
    [string]$Log
)
$ErrorActionPreference = 'Stop'

$root = 'C:\Users\leeza\.cline\data\workspaces\chat\crimson-eye-reaper-scythe'
if (-not (Test-Path -LiteralPath $Blender)) { throw "no Blender at $Blender" }
$build = Join-Path $root 'scene\build.py'
if (-not $Log) { $Log = Join-Path $root ("out\run_{0}.log" -f $Stage) }

$extra = @()
if (-not $Snapshots) { $extra += '--no-snapshot' }

& $Blender --background --factory-startup --python $build -- `
    --stage $Stage @extra 2>&1 | Tee-Object -FilePath $Log

$code = $LASTEXITCODE
Write-Output ("[build_headless] blender exit code {0}; log {1}" -f $code, $Log)

# Summarise every gate the run left behind, so one command tells you the state.
$failed = @()
Get-ChildItem (Join-Path $root 'out') -Filter 's*_response.json' | ForEach-Object {
    $payload = Get-Content $_.FullName -Raw | ConvertFrom-Json
    if ($payload.gate_ok -ne $true) {
        $bad = @()
        if ($payload.checks) {
            $payload.checks.PSObject.Properties |
                Where-Object { -not $_.Value } | ForEach-Object { $bad += $_.Name }
        }
        $failed += ("{0} [{1}]" -f $payload.stage, ($bad -join ', '))
    }
}
if ($failed.Count -eq 0) {
    Write-Output '[build_headless] every gate passed'
} else {
    Write-Output ('[build_headless] FAILED: ' + ($failed -join '; '))
    exit 3
}
exit $code
