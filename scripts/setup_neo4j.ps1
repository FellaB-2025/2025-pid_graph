# Create (or start) the neo4j-kg container and verify the pid_graph environment.
# Usage, from the pid_graph folder, after Docker Desktop is running:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_neo4j.ps1
# Reads NEO4J_PASSWORD (and optionally NEO4J_USER) from .env - never pass the password on the command line.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "No .env found. Copy .env.example to .env and set NEO4J_PASSWORD first."
}
$vars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { $vars[$matches[1]] = $matches[2].Trim('"').Trim("'") }
}
$user = if ($vars.ContainsKey("NEO4J_USER") -and $vars["NEO4J_USER"]) { $vars["NEO4J_USER"] } else { "neo4j" }
$pw = $vars["NEO4J_PASSWORD"]
if (-not $pw -or $pw -eq "change-me") { Write-Error "NEO4J_PASSWORD in .env is empty or still the placeholder." }
if ($pw.Length -lt 8) { Write-Error "Neo4j requires a password of at least 8 characters." }

docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Error "Docker engine is not reachable. Start Docker Desktop and wait for it to say 'Engine running'." }

$existing = docker ps -a --filter "name=^neo4j-kg$" --format "{{.Names}}"
if ($existing -eq "neo4j-kg") {
    Write-Output "Container neo4j-kg exists; starting it."
    docker start neo4j-kg | Out-Null
} else {
    Write-Output "Creating container neo4j-kg (neo4j:5, ports 7474/7687, volume neo4j-kg-data)."
    docker run -d --name neo4j-kg -p 7474:7474 -p 7687:7687 `
        -e "NEO4J_AUTH=$user/$pw" `
        -v neo4j-kg-data:/data `
        --restart unless-stopped `
        neo4j:5 | Out-Null
}

Write-Output "Waiting for bolt on localhost:7687 ..."
$deadline = (Get-Date).AddMinutes(3)
$up = $false
while ((Get-Date) -lt $deadline) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect("localhost", 7687); $c.Close(); $up = $true; break
    } catch { Start-Sleep -Seconds 3 }
}
if (-not $up) { Write-Error "Neo4j did not open port 7687 within 3 minutes. Check: docker logs neo4j-kg" }
Start-Sleep -Seconds 5
Write-Output "Neo4j is listening. Browser UI: http://localhost:7474"
& (Join-Path $root ".venv\Scripts\python.exe") -m pid_graph.check_env
