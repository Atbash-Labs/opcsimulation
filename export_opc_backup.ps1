# OPC UA Backup Export Script
# Exports all nodes/values from an OPC UA server to a JSON backup file

param(
    [string]$ServerUrl = "opc.tcp://localhost:4840",
    [string]$BackupDir = "C:\opcbackup",
    [string]$Username = "",
    [string]$Password = ""
)

# Function to find Python executable
function Find-Python {
    
    # Check if python is already in PATH
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return "python"
    }
    
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        Write-Host "Found Python launcher (py)" -ForegroundColor Gray
        return "py"
    }
    
    # Try using where.exe to find python in PATH
    try {
        $wherePython = where.exe python 2>$null | Select-Object -First 1
        if ($wherePython -and (Test-Path $wherePython)) {
            Write-Host "Found Python via where.exe: $wherePython" -ForegroundColor Gray
            return $wherePython
        }
    } catch {
        # where.exe failed, continue
    }
    
    # Try direct check of common Python versions (Python 3.8-3.12)
    $commonVersions = @("312", "311", "310", "39", "38")
    $usernamesToTry = @()
    if ($env:USERNAME) { $usernamesToTry += $env:USERNAME }
    $usernamesToTry += "leorf"
    $usernamesToTry += "Administrator"
    $usernamesToTry += "imeuspjyfcoe"
    
    foreach ($username in $usernamesToTry) {
        foreach ($version in $commonVersions) {
            $directPath = "C:\Users\$username\AppData\Local\Programs\Python\Python$version\python.exe"
            if (Test-Path $directPath) {
                Write-Host "Found Python at: $directPath" -ForegroundColor Gray
                return $directPath
            }
        }
    }
    
    # Build list of potential Python paths
    $searchPaths = @()
    
    # User-specific paths
    if ($env:USERPROFILE) {
        $searchPaths += "$env:USERPROFILE\AppData\Local\Programs\Python"
        $searchPaths += "$env:USERPROFILE\AppData\Local\Microsoft\WindowsApps"
    }
    
    # Also try with explicit username if USERPROFILE isn't set
    if ($env:USERNAME) {
        $searchPaths += "C:\Users\$env:USERNAME\AppData\Local\Programs\Python"
    }
    
    # Fallback: try hardcoded common usernames if env vars aren't set
    $fallbackUsers = @()
    $fallbackUsers += "leorf"
    $fallbackUsers += "Administrator"
    $fallbackUsers += "imeuspjyfcoe"
    foreach ($username in $fallbackUsers) {
        $searchPaths += "C:\Users\$username\AppData\Local\Programs\Python"
    }
    
    # System-wide paths
    $searchPaths += "$env:ProgramFiles\Python*"
    $searchPaths += "${env:ProgramFiles(x86)}\Python*"
    $searchPaths += "C:\Python*"
    
    # Check LOCALAPPDATA if it's a valid user path (not system profile)
    if ($env:LOCALAPPDATA -and -not $env:LOCALAPPDATA.Contains("system32\config\systemprofile")) {
        $searchPaths += "$env:LOCALAPPDATA\Programs\Python"
    }
    
    # Also check common installation locations directly
    $directPaths = @(
        "C:\Program Files\Python*",
        "C:\Program Files (x86)\Python*"
    )
    if ($env:USERNAME) {
        $directPaths += "C:\Users\$env:USERNAME\AppData\Local\Programs\Python"
    }
    $directPaths += "C:\Users\leorf\AppData\Local\Programs\Python"  # Fallback
    $searchPaths += $directPaths
    
    # Search for python.exe in these paths
    foreach ($pathPattern in $searchPaths) {
        try {
            $found = Get-ChildItem -Path $pathPattern -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue | 
                     Where-Object { $_.FullName -notlike "*WindowsApps*" } | 
                     Select-Object -First 1
            if ($found -and (Test-Path $found.FullName)) {
                Write-Host "Found Python at: $($found.FullName)" -ForegroundColor Gray
                return $found.FullName
            }
        } catch {
            # Continue searching
        }
    }
    
    # Try registry lookup (for installed Python versions)
    try {
        $pythonRegPaths = @(
            "HKLM:\SOFTWARE\Python\PythonCore\*\InstallPath",
            "HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore\*\InstallPath"
        )
        
        foreach ($regPath in $pythonRegPaths) {
            $installPaths = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
            foreach ($installPath in $installPaths) {
                $pythonExe = Join-Path $installPath.ExecutablePath "python.exe"
                if (Test-Path $pythonExe) {
                    Write-Host "Found Python via registry: $pythonExe" -ForegroundColor Gray
                    return $pythonExe
                }
            }
        }
    } catch {
        # Registry lookup failed, continue
    }
    
    # Last resort: try py launcher (but this often fails in automated contexts)
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        Write-Host "Warning: Using 'py' launcher - may fail in automated contexts" -ForegroundColor Yellow
        return "py"
    }
    
    return $null
}

# Ensure Python is available
$pythonExe = Find-Python
if (-not $pythonExe) {
    Write-Host "Error: Python not found. Please install Python or add it to your PATH." -ForegroundColor Red
    Write-Host "Common Python locations:" -ForegroundColor Yellow
    Write-Host "  - $env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ForegroundColor Gray
    Write-Host "  - $env:ProgramFiles\Python*\python.exe" -ForegroundColor Gray
    exit 1
}

# Add Python directory to PATH for this session if using full path
if ($pythonExe -ne "python") {
    $pythonDir = Split-Path -Parent $pythonExe
    if ($env:PATH -notlike "*$pythonDir*") {
        $env:PATH = "$pythonDir;$env:PATH"
        Write-Host "Added Python to PATH: $pythonDir" -ForegroundColor Gray
    }
}

# Create backup directory if it doesn't exist
if (-not (Test-Path -Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    Write-Host "Created backup directory: $BackupDir" -ForegroundColor Green
}


$filename = "opc_backup_export.json"
$backupPath = Join-Path $BackupDir $filename

Write-Host "Starting OPC UA export..." -ForegroundColor Cyan
Write-Host "  Server: $ServerUrl" -ForegroundColor Gray
Write-Host "  Output: $backupPath" -ForegroundColor Gray

# Get script directory for Python scripts
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Install dependencies from C:\opcbackup\requirements.txt
$requirementsPath = Join-Path $BackupDir "requirements.txt"

if (Test-Path $requirementsPath) {
    Write-Host "Installing Python dependencies from $requirementsPath..." -ForegroundColor Gray
    try {
        & $pythonExe -m pip install -q -r $requirementsPath 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Dependencies installed successfully" -ForegroundColor Gray
        }
    } catch {
        Write-Host "Warning: Could not install dependencies, continuing anyway..." -ForegroundColor Yellow
    }
} else {
    Write-Host "Warning: requirements.txt not found at $requirementsPath" -ForegroundColor Yellow
}

# Build command arguments
$scriptArgs = @(
    (Join-Path $scriptDir "export_opc_nodes.py")
    "--source-url", $ServerUrl
    "--output-file", $backupPath
)

# Add authentication if provided
if ($Username -ne "") {
    $scriptArgs += "--username", $Username
}
if ($Password -ne "") {
    $scriptArgs += "--password", $Password
}

# Run the export script
try {
    & $pythonExe $scriptArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nExport completed successfully!" -ForegroundColor Green
        Write-Host "Backup saved to: $backupPath" -ForegroundColor Green
        
        # Get file size
        $fileSize = (Get-Item $backupPath).Length / 1KB
        Write-Host "File size: $([math]::Round($fileSize, 2)) KB" -ForegroundColor Gray
    } else {
        Write-Host "`nExport failed with exit code: $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "`nError running export script: $_" -ForegroundColor Red
    exit 1
}

