function Get-AllPythonVersions {
    $output = py -0p 2>&1
    $allVersions = @()
    if ($output) {
        foreach ($line in $output) {
            if ($line -match "(\d+\.\d+\.\d+)") {
                $allVersions += $line.Trim()
            }
        }
    }
    return $allVersions
}

function IsPythonVersionValid($version) {
    if ([version]$version -ge [version]"3.10.0" -and [version]$version -lt [version]"3.11.0") {
        return $true
    }
    return $false
}

Write-Host "Searching for a valid Python version..."
$selectedPythonPath = $null
$allPythonVersions = Get-AllPythonVersions

foreach ($pythonPath in $allPythonVersions) {
    $versionMatch = ($pythonPath -match "(\d+\.\d+\.\d+)")
    if ($versionMatch -and (IsPythonVersionValid($matches[1]))) {
        $selectedPythonPath = $pythonPath
        Write-Host "Found suitable Python version: $matches[1]"
        break
    }
}

if (-not $selectedPythonPath) {
    Write-Host "No suitable Python version found. Installing Python 3.10 using winget..."
    winget install --id "Python.Python.3.10" -e --silent
    
    $allPythonVersions = Get-AllPythonVersions
    foreach ($pythonPath in $allPythonVersions) {
        $versionMatch = ($pythonPath -match "(\d+\.\d+\.\d+)")
        if ($versionMatch -and (IsPythonVersionValid($matches[1]))) {
            $selectedPythonPath = $pythonPath
            Write-Host "Found suitable Python version after installation: $matches[1]"
            break
        }
    }
    
    if (-not $selectedPythonPath) {
        Write-Host "Python installation failed or did not meet requirements. Please check manually."
        exit 1
    }
}

Write-Host "Creating a Python virtual environment with the selected Python version..."
& "$selectedPythonPath" -m venv env

Write-Host "Activating the virtual environment..."
& env\Scripts\Activate.ps1

if (Test-Path "requirements.txt") {
    Write-Host "Installing packages from requirements.txt..."
    pip install -r requirements.txt
} else {
    Write-Host "requirements.txt not found. Cannot install packages."
    exit 1
}

if (Test-Path "main.py") {
    Write-Host "Running main.py using the py launcher..."
    py main.py
} else {
    Write-Host "main.py not found. Cannot execute the script."
    exit 1
}
