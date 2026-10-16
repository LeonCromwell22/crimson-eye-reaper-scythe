# Run one scythe stage inside the live Blender session.
#
# WHY THIS EXISTS
#   The "MCP for Blender" add-on serves a JSON command channel on
#   127.0.0.1:9876 (see overgrown-observatory/tools/live/bridge.ps1, which is the
#   transport). This wrapper turns "run stage s14_paint" into exactly one payload
#   and one response file, so every stage leaves the same evidence behind and a
#   failure is attributable to one call.
#
#   Stages are cumulative: asking for s16 runs s0..s16 in order.
#
# USAGE
#   powershell -NoProfile -File tools/run_stage.ps1 -Stage s14_paint
#   powershell -NoProfile -File tools/run_stage.ps1 -Stage s13_bake -TimeoutMs 1800000
#
# NOTE
#   This runs in whatever scene the open Blender has - and s0_setup starts with
#   read_factory_settings, which DISCARDS WORK IN PROGRESS. Save first, or use
#   build_headless.ps1, which cannot disturb a session.
param(
    [Parameter(Mandatory = $true)][string]$Stage,
    [int]$TimeoutMs = 900000,
    [string]$Response
)
$ErrorActionPreference = 'Stop'

$root = 'C:\Users\leeza\.cline\data\workspaces\chat\crimson-eye-reaper-scythe'
$bridge = 'C:\Users\leeza\.cline\data\workspaces\chat\overgrown-observatory\tools\live\bridge.ps1'
if (-not (Test-Path -LiteralPath $bridge)) { throw "no bridge at $bridge" }
if (-not $Response) { $Response = Join-Path $root ("out\{0}_response.json" -f $Stage) }
if (-not (Test-Path -LiteralPath (Split-Path -Parent $Response))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Response) | Out-Null
}

$code = "import sys; sys.argv = ['build.py', '--', '--stage', '$Stage', '--no-snapshot']; exec(open(r'$root\scene\build.py', encoding='utf-8').read())"
$req = @{ type = 'execute_code'; params = @{ code = $code } } | ConvertTo-Json -Depth 6 -Compress
$reqPath = Join-Path $env:TEMP ("scythe_{0}_req.json" -f $Stage)
[System.IO.File]::WriteAllText($reqPath, $req, (New-Object System.Text.UTF8Encoding($false)))

& $bridge -Request $reqPath -Response $Response -TimeoutMs $TimeoutMs

$payload = Get-Content -LiteralPath $Response -Raw | ConvertFrom-Json
if ($payload.status -ne 'success') {
    Write-Output ("STAGE FAILED: " + $payload.status)
    $payload | ConvertTo-Json -Depth 8
    exit 1
}
if ($payload.result.executed -ne $true) {
    Write-Output 'STAGE FAILED: code did not execute'
    Write-Output $payload.result.result
    exit 1
}
Write-Output $payload.result.result
