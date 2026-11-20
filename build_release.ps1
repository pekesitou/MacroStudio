# Macro Studio - reproducible release build (executable + portable + installer)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host "`n[1/5] Compilando ejecutable con PyInstaller..." -ForegroundColor Cyan
function Stop-RunningApp {
    Get-Process -Name MacroStudio,MacroStudio-NoInstall -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 400
}
# PyInstaller cannot overwrite a locked exe: remove the old one ourselves.
$exe = 'dist\MacroStudio-NoInstall.exe'
for ($i = 0; $i -lt 8 -and (Test-Path $exe); $i++) {
    Stop-RunningApp
    try { Remove-Item $exe -Force -ErrorAction Stop } catch { Start-Sleep -Milliseconds 500 }
}
if (Test-Path $exe) { throw "No se pudo liberar $exe - cierra Macro Studio antes de compilar" }
python -m PyInstaller --noconfirm --clean --onefile --noconsole `
    --name "MacroStudio-NoInstall" `
    --icon "assets/macro_studio.ico" `
    --add-data "assets/macro_studio.ico;assets" `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo con codigo $LASTEXITCODE" }

Write-Host "`n[2/5] Copiando licencias y guia de entregables..." -ForegroundColor Cyan
foreach ($doc in @('LICENSE', 'THIRD_PARTY_NOTICES.md')) {
    Copy-Item $doc -Destination "dist\$doc" -Force
}
Copy-Item 'DIST_README.md' -Destination 'dist\README.md' -Force

Write-Host "`n[3/5] Creando version portable..." -ForegroundColor Cyan
$portable = 'dist\MacroStudio_Portable'
if (Test-Path $portable) { Remove-Item $portable -Recurse -Force }
New-Item -ItemType Directory -Path $portable -Force | Out-Null
Copy-Item 'dist\MacroStudio-NoInstall.exe' -Destination "$portable\MacroStudio.exe" -Force
foreach ($doc in @('LICENSE', 'THIRD_PARTY_NOTICES.md')) {
    Copy-Item $doc -Destination $portable -Force
}
Copy-Item 'DIST_README.md' -Destination "$portable\README.md" -Force
# This marker makes the app store its data in .\data instead of %APPDATA%.
Set-Content -Path "$portable\portable.txt" -Value "Macro Studio - portable mode" -Encoding ASCII
if (Test-Path 'dist\MacroStudio_Portable.zip') { Remove-Item 'dist\MacroStudio_Portable.zip' -Force }
Compress-Archive -Path "$portable\*" -DestinationPath 'dist\MacroStudio_Portable.zip' -CompressionLevel Optimal

Write-Host "`n[4/5] Compilando instalador con Inno Setup..." -ForegroundColor Cyan
$iscc = $null
foreach ($candidate in @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)) {
    if (Test-Path $candidate) { $iscc = $candidate; break }
}
if (-not $iscc) {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) { $iscc = $command.Source }
}
if (-not $iscc) {
    Write-Warning "Inno Setup no encontrado; omitiendo instalador."
} else {
    & $iscc "installer\MacroStudio.iss"
    if ($LASTEXITCODE -ne 0) { throw "ISCC fallo con codigo $LASTEXITCODE" }
}

Write-Host "`n[5/5] Generando SHA256SUMS.txt..." -ForegroundColor Cyan
$sums = Get-ChildItem 'dist' -File -Filter '*.exe' |
    Sort-Object Name | ForEach-Object {
        $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $($_.Name)"
    }
Set-Content -Path 'dist\SHA256SUMS.txt' -Value $sums -Encoding ASCII

Write-Host "`nLISTO. Entregables en dist\:" -ForegroundColor Green
Get-ChildItem 'dist' -File | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB, 2)}} |
    Format-Table -AutoSize | Out-Host
