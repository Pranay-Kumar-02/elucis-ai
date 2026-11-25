<#
.SYNOPSIS
  Phase A - read-only machine inventory for Elucis AI.

.DESCRIPTION
  Detects OS, hardware, GPU, and every tool the project needs, and writes
  .setup-reports/inventory.json and .setup-reports/inventory.md.

  Read-only: installs nothing, changes nothing, needs no administrator rights.
  Prints no secrets: environment variables are reported by NAME only, never by value
  (PATH entries are the one exception, because they are directory names).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\00-inventory.ps1
#>
[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ReportDir = Join-Path $ProjectRoot '.setup-reports'
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

function Invoke-Probe {
    # Runs an executable with a timeout and returns trimmed stdout+stderr, or $null if missing.
    param([string]$Exe, [string[]]$Arguments = @(), [int]$TimeoutSec = 20)
    $cmd = Get-Command $Exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $cmd) { return $null }
    $path = $cmd.Source
    if ($cmd.CommandType -eq 'Alias' -or $cmd.CommandType -eq 'Function') { return $null }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $path
        $psi.Arguments = ($Arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $outTask = $p.StandardOutput.ReadToEndAsync()
        $errTask = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            try { $p.Kill() } catch {}
            return "TIMEOUT after ${TimeoutSec}s"
        }
        $text = ($outTask.Result + "`n" + $errTask.Result).Trim()
        # wsl.exe writes UTF-16; strip NULs so the text is readable.
        return ($text -replace "`0", '')
    } catch {
        return "ERROR: $($_.Exception.Message)"
    }
}

function Get-ToolInfo {
    param([string]$Name, [string]$Exe, [string[]]$VersionArgs = @('--version'))
    $all = @(Get-Command $Exe -All -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' } |
            ForEach-Object { $_.Source } | Select-Object -Unique)
    $ver = $null
    if ($all.Count -gt 0) { $ver = Invoke-Probe -Exe $Exe -Arguments $VersionArgs }
    [ordered]@{
        name      = $Name
        found     = ($all.Count -gt 0)
        version   = $ver
        paths     = $all
    }
}

$inv = [ordered]@{}
$inv.generated_at = (Get-Date).ToString('o')
$inv.script_version = '1.0.0'
$inv.project_root = $ProjectRoot

# ---------- OS ----------
$os = Get-CimInstance Win32_OperatingSystem
$cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue
$inv.os = [ordered]@{
    caption        = $os.Caption
    version        = $os.Version
    build          = $os.BuildNumber
    display_version = $(if ($cv -and ($cv.PSObject.Properties.Name -contains 'DisplayVersion')) { $cv.DisplayVersion } else { $null })
    ubr            = $(if ($cv -and ($cv.PSObject.Properties.Name -contains 'UBR')) { $cv.UBR } else { $null })
    architecture   = $os.OSArchitecture
    powershell     = $PSVersionTable.PSVersion.ToString()
    is_admin       = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    execution_policy = (Get-ExecutionPolicy -Scope CurrentUser).ToString()
    long_paths_enabled = $(try { (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction Stop).LongPathsEnabled -eq 1 } catch { $false })
    user_profile_has_space = ($env:USERPROFILE -match '\s')
}

# ---------- Hardware ----------
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs = Get-CimInstance Win32_ComputerSystem
$inv.hardware = [ordered]@{
    cpu_name        = $cpu.Name.Trim()
    cores           = $cpu.NumberOfCores
    logical_processors = $cpu.NumberOfLogicalProcessors
    ram_total_gb    = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
    ram_free_gb     = [math]::Round($os.FreePhysicalMemory * 1KB / 1GB, 2)
    virtualization_firmware_enabled = $(try { $cpu.VirtualizationFirmwareEnabled } catch { $null })
    hypervisor_present = $cs.HypervisorPresent
}
$inv.disks = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    [ordered]@{ drive = $_.DeviceID; size_gb = [math]::Round($_.Size / 1GB, 1); free_gb = [math]::Round($_.FreeSpace / 1GB, 1); fs = $_.FileSystem }
})

# ---------- GPU ----------
$inv.gpu = [ordered]@{
    adapters   = @(Get-CimInstance Win32_VideoController | ForEach-Object { [ordered]@{ name = $_.Name; driver = $_.DriverVersion } })
    nvidia_smi = Invoke-Probe -Exe 'nvidia-smi' -Arguments @('--query-gpu=name,memory.total,memory.used,memory.free,driver_version', '--format=csv,noheader')
    cuda_header = $(($(Invoke-Probe -Exe 'nvidia-smi') -split "`n" | Select-String -Pattern 'CUDA Version' | Select-Object -First 1) -as [string])
}

# ---------- Tools ----------
$inv.tools = [ordered]@{
    py_launcher  = Get-ToolInfo 'Python launcher' 'py' @('--version')
    py_list      = Invoke-Probe -Exe 'py' -Arguments @('-0p')
    python       = Get-ToolInfo 'python on PATH' 'python' @('--version')
    python3      = Get-ToolInfo 'python3 on PATH' 'python3' @('--version')
    uv           = Get-ToolInfo 'uv' 'uv' @('--version')
    uv_pythons   = Invoke-Probe -Exe 'uv' -Arguments @('python', 'list', '--only-installed')
    node         = Get-ToolInfo 'Node.js' 'node' @('--version')
    npm          = Get-ToolInfo 'npm' 'npm.cmd' @('--version')
    pnpm         = Get-ToolInfo 'pnpm' 'pnpm.cmd' @('--version')
    corepack     = Get-ToolInfo 'corepack' 'corepack.cmd' @('--version')
    git          = Get-ToolInfo 'Git' 'git' @('--version')
    vscode       = Get-ToolInfo 'VS Code' 'code.cmd' @('--version')
    psql         = Get-ToolInfo 'psql' 'psql' @('--version')
    pg_config    = Get-ToolInfo 'pg_config' 'pg_config' @('--version')
    docker       = Get-ToolInfo 'Docker CLI' 'docker' @('--version')
    wsl          = Get-ToolInfo 'WSL' 'wsl' @('--version')
    wsl_status   = Invoke-Probe -Exe 'wsl' -Arguments @('--status')
    wsl_list     = Invoke-Probe -Exe 'wsl' -Arguments @('--list', '--verbose')
    ollama       = Get-ToolInfo 'Ollama' 'ollama' @('--version')
    ollama_list  = Invoke-Probe -Exe 'ollama' -Arguments @('list')
    winget       = Get-ToolInfo 'winget' 'winget' @('--version')
    nmake        = Get-ToolInfo 'nmake (MSVC)' 'nmake' @('/?')
}

# PostgreSQL installed outside PATH (EDB installer default location)
$pgDirs = @()
foreach ($base in @("$env:ProgramFiles\PostgreSQL", "${env:ProgramFiles(x86)}\PostgreSQL")) {
    if ($base -and (Test-Path $base)) {
        Get-ChildItem $base -Directory | ForEach-Object {
            $pgc = Join-Path $_.FullName 'bin\pg_config.exe'
            $ver = $null
            if (Test-Path $pgc) { $ver = Invoke-Probe -Exe $pgc -Arguments @('--version') }
            $vecCtl = Join-Path $_.FullName 'share\extension\vector.control'
            $vecVer = $null
            if (Test-Path $vecCtl) { $vecVer = (Select-String -Path $vecCtl -Pattern "default_version" | Select-Object -First 1).Line }
            $pgDirs += [ordered]@{ dir = $_.FullName; pg_config = $ver; pgvector_control = $vecVer }
        }
    }
}
$inv.postgresql_installs = $pgDirs
$inv.postgresql_services = @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'postgresql*' } |
    ForEach-Object { [ordered]@{ name = $_.Name; status = $_.Status.ToString(); start_type = $_.StartType.ToString() } })
$inv.port_5432_listening = [bool](Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue)

# Visual Studio Build Tools (needed only for a native pgvector build)
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$inv.visual_studio = $null
if (Test-Path $vswhere) {
    $inv.visual_studio = Invoke-Probe -Exe $vswhere -Arguments @('-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-format', 'json')
}

# Docker Desktop
$inv.docker_desktop_installed = (Test-Path "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe")
$inv.docker_engine = $null
if ($inv.tools.docker.found) { $inv.docker_engine = Invoke-Probe -Exe 'docker' -Arguments @('info', '--format', '{{.ServerVersion}} {{.OperatingSystem}}') -TimeoutSec 15 }

# Ollama runtime
$ollama = [ordered]@{ api_reachable = $false; version = $null; models = $null; env_names = @() }
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 5
    $ollama.api_reachable = $true
    $ollama.version = $r.version
    $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10
    $ollama.models = @($tags.models | ForEach-Object { [ordered]@{ name = $_.name; size_gb = [math]::Round($_.size / 1GB, 2); digest = $_.digest.Substring(0, 12); modified = $_.modified_at } })
} catch { $ollama.error = $_.Exception.Message }
$ollama.env_names = @(Get-ChildItem Env: | Where-Object { $_.Name -like 'OLLAMA_*' } | ForEach-Object { $_.Name })
# OLLAMA_* values are configuration, not secrets; record them so the model setup is reproducible.
$ollama.env = [ordered]@{}
foreach ($n in $ollama.env_names) { $ollama.env[$n] = (Get-Item "Env:$n").Value }
$inv.ollama = $ollama

# ---------- Project folder location ----------
$oneDriveRoots = @($env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial) | Where-Object { $_ } | Select-Object -Unique
$inOneDrive = $false
foreach ($r in $oneDriveRoots) { if ($ProjectRoot.StartsWith($r, [StringComparison]::OrdinalIgnoreCase)) { $inOneDrive = $true } }
$inv.project_location = [ordered]@{
    path          = $ProjectRoot
    inside_onedrive = $inOneDrive
    path_has_space  = ($ProjectRoot -match '\s')
    existing_items  = @(Get-ChildItem -Force $ProjectRoot | ForEach-Object { $_.Name })
}

# ---------- Environment variables (names only) ----------
$secretish = '(?i)(KEY|TOKEN|SECRET|PASS|PWD|CRED|AUTH|COOKIE|SESSION)'
$inv.env_var_names = @(Get-ChildItem Env: | ForEach-Object { $_.Name } | Sort-Object)
$inv.env_var_names_that_look_secret = @($inv.env_var_names | Where-Object { $_ -match $secretish })
$inv.path_entries = @(($env:PATH -split ';') | Where-Object { $_ } | Select-Object -Unique)
$inv.relevant_env_present = [ordered]@{}
foreach ($n in @('VIRTUAL_ENV', 'CONDA_PREFIX', 'PYTHONPATH', 'PYTHONHOME', 'UV_PYTHON', 'NODE_OPTIONS', 'PGDATA', 'PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'DATABASE_URL', 'HTTP_PROXY', 'HTTPS_PROXY')) {
    $inv.relevant_env_present[$n] = [bool](Test-Path "Env:$n")
}

# ---------- Write reports ----------
$jsonPath = Join-Path $ReportDir 'inventory.json'
$inv | ConvertTo-Json -Depth 8 | Out-File -FilePath $jsonPath -Encoding utf8

$md = New-Object System.Collections.Generic.List[string]
$md.Add('# Machine inventory')
$md.Add('')
$md.Add("Generated: $($inv.generated_at)")
$md.Add('')
$md.Add('| Item | Result |')
$md.Add('|---|---|')
$md.Add("| OS | $($inv.os.caption) $($inv.os.display_version) build $($inv.os.build).$($inv.os.ubr) $($inv.os.architecture) |")
$md.Add("| CPU | $($inv.hardware.cpu_name) ($($inv.hardware.cores) cores / $($inv.hardware.logical_processors) threads) |")
$md.Add("| RAM | $($inv.hardware.ram_total_gb) GB total, $($inv.hardware.ram_free_gb) GB free now |")
foreach ($d in $inv.disks) { $md.Add("| Disk $($d.drive) | $($d.free_gb) GB free of $($d.size_gb) GB |") }
$md.Add("| NVIDIA | $($inv.gpu.nvidia_smi) |")
foreach ($k in $inv.tools.Keys) {
    $t = $inv.tools[$k]
    if ($t -is [System.Collections.IDictionary]) {
        $v = if ($t.found) { (($t.version -split "`n")[0]) } else { 'NOT FOUND' }
        $md.Add("| $($t.name) | $v |")
    }
}
$md.Add("| PostgreSQL installs | $(($inv.postgresql_installs | ForEach-Object { $_.pg_config + ' / ' + $_.pgvector_control }) -join '; ') |")
$md.Add("| Ollama API | reachable=$($inv.ollama.api_reachable) version=$($inv.ollama.version) |")
$md.Add("| Project in OneDrive | $($inv.project_location.inside_onedrive) |")
$md.Add('')
$md.Add('Full details: inventory.json')
$md | Out-File -FilePath (Join-Path $ReportDir 'inventory.md') -Encoding utf8

Write-Host ''
Write-Host "Inventory written to $ReportDir" -ForegroundColor Green
Write-Host 'Nothing was installed or changed. You can tell Claude it is done.'
