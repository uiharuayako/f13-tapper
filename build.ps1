param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath ".build-venv\Scripts\python.exe")) {
    & $Python -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the build environment." }
}
$buildPython = Join-Path $PSScriptRoot ".build-venv\Scripts\python.exe"
& $buildPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw "Could not initialize pip." }
& $buildPython -m pip install --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install build dependencies." }
& $buildPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
$versionPath = Join-Path $PSScriptRoot "version_info.txt"
& $buildPython -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name F13Tapper --version-file $versionPath --specpath build --workpath build\pyinstaller --distpath dist f13_gui.py
if ($LASTEXITCODE -ne 0) { throw "Packaging failed." }
$exePath = Join-Path $PSScriptRoot "dist\F13Tapper.exe"
$reportPath = Join-Path $PSScriptRoot "build\exe-smoke-test.json"
$checkProcess = Start-Process -FilePath $exePath -ArgumentList @("--smoke-test", ('"' + $reportPath + '"')) -WindowStyle Hidden -PassThru
if (-not $checkProcess.WaitForExit(30000)) {
    $checkProcess.Kill()
    throw "EXE smoke test timed out."
}
if ($checkProcess.ExitCode -ne 0) { throw "EXE smoke test failed; see $reportPath" }
if (-not (Test-Path -LiteralPath $reportPath)) { throw "EXE produced no smoke-test report." }
$smokeReport = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($smokeReport.ok -ne $true) { throw "EXE reported a failed smoke test; see $reportPath" }
$exeHash = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "dist\SHA256SUMS.txt" -Value "$exeHash  F13Tapper.exe" -Encoding ascii
Write-Output "Build and EXE smoke test passed: $exePath"
Write-Output "SHA-256: $exeHash"
