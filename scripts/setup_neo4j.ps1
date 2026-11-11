# Create (or start) pid_graph's own Neo4j container and verify the environment.
# (c) 2026 Alan Bowden - Bowden Simulators. All rights reserved.
#
# Usage, from the pid_graph folder, after Docker Desktop is running:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_neo4j.ps1
#
# pid_graph has its own container so that it never shares a database with another project
# (Neo4j Community holds one database per container; kg_suppression uses neo4j-kg on 7474/7687).
#
# Settings, each read from the environment first, then from .env, then the default:
#   NEO4J_CONTAINER   container name                  default neo4j-pidgraph  (data volume: <name>-data)
#   NEO4J_URI         bolt://localhost:<bolt port>    default bolt://localhost:7688
#   NEO4J_HTTP_PORT   Neo4j Browser port              default 7475
#   NEO4J_USER        default neo4j
#   NEO4J_PASSWORD    from .env only - never pass the password on the command line.

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
function Setting($name, $default) {
    $fromEnv = [Environment]::GetEnvironmentVariable($name)
    if ($fromEnv) { return $fromEnv }
    if ($vars.ContainsKey($name) -and $vars[$name]) { return $vars[$name] }
    return $default
}
$user = Setting "NEO4J_USER" "neo4j"
$pw = $vars["NEO4J_PASSWORD"]
if (-not $pw -or $pw -eq "change-me") { Write-Error "NEO4J_PASSWORD in .env is empty or still the placeholder." }
if ($pw.Length -lt 8) { Write-Error "Neo4j requires a password of at least 8 characters." }

$name = Setting "NEO4J_CONTAINER" "neo4j-pidgraph"
$uri = Setting "NEO4J_URI" "bolt://localhost:7688"
$http = [int](Setting "NEO4J_HTTP_PORT" "7475")
if ($uri -notmatch ':(\d+)\s*$') { Write-Error "NEO4J_URI '$uri' has no port. Expected something like bolt://localhost:7688." }
$bolt = [int]$matches[1]

docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Error "Docker engine is not reachable. Start Docker Desktop and wait for it to say 'Engine running'." }

# Refuse to sit on another container's ports: that is how two projects end up in one database.
$others = docker ps -a --format "{{.Names}}|{{.Ports}}" | Where-Object { $_ -and ($_ -notmatch "^$([regex]::Escape($name))\|") }
foreach ($o in $others) {
    if ($o -match ":$bolt->" -or $o -match ":$http->") {
        $other = $o.Split("|")[0]
        Write-Error ("Port $bolt or $http is already published by container '$other'. pid_graph must not share it. " +
                     "Set NEO4J_URI=bolt://localhost:7688 and NEO4J_HTTP_PORT=7475 in .env (or choose other free ports) and run this again.")
    }
}

$existing = docker ps -a --filter "name=^$name$" --format "{{.Names}}"
if ($existing -eq $name) {
    Write-Output "Container $name exists; starting it."
    docker start $name | Out-Null
} else {
    Write-Output "Creating container $name (neo4j:5, ports $http/$bolt, volume $name-data)."
    docker run -d --name $name -p "${http}:7474" -p "${bolt}:7687" `
        -e "NEO4J_AUTH=$user/$pw" `
        -v "${name}-data:/data" `
        --restart unless-stopped `
        neo4j:5 | Out-Null
}

Write-Output "Waiting for bolt on localhost:$bolt ..."
$deadline = (Get-Date).AddMinutes(3)
$up = $false
while ((Get-Date) -lt $deadline) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect("localhost", $bolt); $c.Close(); $up = $true; break
    } catch { Start-Sleep -Seconds 3 }
}
if (-not $up) { Write-Error "Neo4j did not open port $bolt within 3 minutes. Check: docker logs $name" }
$env:NEO4J_URI = $uri
$env:NEO4J_CONTAINER = $name
# Docker opens the port before Neo4j answers on it (a new container takes longer): wait for a real connection.
$py = Join-Path $root ".venv\Scripts\python.exe"
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
$ErrorActionPreference = "Continue"
while ((Get-Date) -lt $deadline) {
    & $py -m pid_graph.db *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 4
}
$ErrorActionPreference = "Stop"
if (-not $ready) { Write-Output "Neo4j has not accepted a connection yet; the check below will say why. Check: docker logs $name" }
Write-Output "Neo4j is listening. Browser UI: http://localhost:$http"
& (Join-Path $root ".venv\Scripts\python.exe") -m pid_graph.check_env
