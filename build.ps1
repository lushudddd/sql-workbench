param(
    [string]$Python = "python",
    [string]$Compiler = (Join-Path $PSScriptRoot ".build-tools\inno\ISCC.exe")
)

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
$originalPythonPath = $env:PYTHONPATH
try {
    $localPackages = @(".build-tools", ".deps") |
        ForEach-Object { Join-Path $PSScriptRoot $_ } |
        Where-Object { Test-Path -LiteralPath $_ }
    $env:PYTHONPATH = (@($localPackages) + @($originalPythonPath) |
        Where-Object { $_ }) -join [IO.Path]::PathSeparator
    & $Python -m PyInstaller --noconfirm --onedir --windowed --name SQLWorkbench `
        --collect-submodules mysql.connector.plugins --collect-data mysql.connector `
        --collect-all oracledb app.py
    if ($LASTEXITCODE) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

    $app = Start-Process -FilePath "dist\SQLWorkbench\SQLWorkbench.exe" `
        -ArgumentList "--verify-package" -Wait -PassThru
    if ($app.ExitCode) { throw "Application verification failed with exit code $($app.ExitCode)." }

    & $Compiler installer.iss
    if ($LASTEXITCODE) { throw "Installer build failed with exit code $LASTEXITCODE." }
} finally {
    $env:PYTHONPATH = $originalPythonPath
    Pop-Location
}
