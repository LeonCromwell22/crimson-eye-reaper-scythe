# Run a Luau snippet in the open Studio session and print what it returned.
#
# WHY THIS EXISTS
#   `execute_luau` needs `code`, `datamodel_type` and `studio_id`, and the code
#   is multi-line Luau - which is miserable to pass through a command line. This
#   wraps a .lua file into a proper args JSON (escaping handled by ConvertTo-Json),
#   calls roblox-bridge/mcp-call.ps1, and prints the tool's text result.
#
# USAGE
#   powershell -NoProfile -File tools/studio/run_luau.ps1 -Lua inspect_model
#   powershell -NoProfile -File tools/studio/run_luau.ps1 -Lua build_tool -DataModel Edit
#
#   -Lua accepts a bare name (looked up as out/studio/<name>.lua) or a full path.
param(
    [Parameter(Mandatory = $true)][string]$Lua,
    [string]$DataModel = 'Edit',
    [string]$Response,
    [string]$Root = 'C:\Users\leeza\.cline\data\workspaces\chat'
)
$ErrorActionPreference = 'Stop'

$project = Join-Path $Root 'crimson-eye-reaper-scythe'
$bridge = Join-Path $Root 'roblox-bridge\mcp-call.ps1'
if (-not (Test-Path -LiteralPath $bridge)) { throw "no bridge at $bridge" }

$script = $Lua
if (-not (Test-Path -LiteralPath $script)) {
    $script = Join-Path $project ("out\studio\{0}.lua" -f $Lua)
}
if (-not (Test-Path -LiteralPath $script)) { throw "no such Luau file: $Lua" }

$name = [System.IO.Path]::GetFileNameWithoutExtension($script)
$studio_dir = Join-Path $project 'out\studio'
if (-not $Response) { $Response = Join-Path $studio_dir ("{0}_response.json" -f $name) }
$argsPath = Join-Path $studio_dir ("{0}_args.json" -f $name)

$code = [System.IO.File]::ReadAllText($script)
$json = @{ datamodel_type = $DataModel; code = $code } |
    ConvertTo-Json -Depth 4 -Compress
[System.IO.File]::WriteAllText($argsPath, $json, (New-Object System.Text.UTF8Encoding($false)))

& $bridge -Tool execute_luau -ArgsFile $argsPath -Response $Response | Out-Null

$payload = Get-Content -LiteralPath $Response -Raw | ConvertFrom-Json
if ($payload.error) {
    Write-Output ("LUAU RPC ERROR: " + ($payload.error | ConvertTo-Json -Compress))
    exit 1
}
if (-not $payload.result) {
    Write-Output 'LUAU RPC ERROR: no result'
    $payload | ConvertTo-Json -Depth 8
    exit 1
}
$isError = $false
if ($payload.result.isError) { $isError = $true }
foreach ($item in $payload.result.content) {
    if ($item.type -eq 'text') { Write-Output $item.text }
}
if ($isError) { exit 2 }
