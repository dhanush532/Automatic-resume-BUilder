param([string]$EnvFile = '.env')
$ErrorActionPreference = 'Stop'

# Inspect staged paths and local secret values without printing their contents.
$paths = @(git ls-files --cached)
if ($LASTEXITCODE -ne 0 -or $paths.Count -eq 0) { throw 'No Git files available to audit.' }
$values = @()
if (Test-Path -LiteralPath $EnvFile) {
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        if ($line -match '^([A-Z0-9_]+)=(.*)$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim().Trim([char[]]@('"', "'"))
            if ($key -match 'AUTH_SECRET|CLIENT_ID|CLIENT_SECRET|API_KEY|PASSWORD|ACCESS_KEY|SMTP_USERNAME|DATABASE_URL|REDIS_URL' -and $value.Length -ge 8) {
                if ($value -match '^(replace-with-|your[_-]|paste[_-])' -or $value -eq 'postgresql+psycopg://careerpilot:careerpilot@localhost:5432/careerpilot' -or $value -eq 'redis://localhost:6379/0') { continue }
                $values += $value
            }
        }
    }
}
$problems = @()
foreach ($file in $paths) {
    $normalized = $file.Replace('\', '/')
    $basename = [IO.Path]::GetFileName($normalized)
    if (($basename -eq '.env' -or $basename.StartsWith('.env.')) -and $basename -ne '.env.example') { $problems += "$file : environment file"; continue }
    if ($normalized -match '(^|/)(node_modules|\.venv|\.next|\.next-dev|\.runtime|\.checkpoints|\.vercel|__pycache__|\.pytest_cache|\.ruff_cache)(/|$)' -or $normalized -match '\.(dump|log|pyc|sqlite3|db)$') { $problems += "$file : private/generated file"; continue }
    # Audit exactly the staged blob, not a possibly newer working file.
    $contents = (git show ":$file") -join "`n"
    if ($LASTEXITCODE -ne 0) { throw "Could not audit staged file: $file" }
    if ($contents -match 'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}') { $problems += "$file : credential pattern"; continue }
    foreach ($value in $values) {
        if ($contents.Contains($value)) { $problems += "$file : matches a local credential"; break }
    }
}
if ($problems.Count -gt 0) {
    $problems | Write-Output
    throw 'Publication audit failed. No credential values were printed.'
}
Write-Output "Publication audit passed: $($paths.Count) staged files; private/generated paths and configured local credentials excluded."
