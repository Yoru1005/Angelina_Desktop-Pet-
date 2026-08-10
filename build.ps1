$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDir = Join-Path $projectDir 'dist'

py -m pip install -r (Join-Path $projectDir 'requirements.txt')
py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name 'Angelina桌寵' `
    --distpath $outputDir `
    --workpath (Join-Path $projectDir 'build') `
    --specpath $projectDir `
    --add-data "$(Join-Path $projectDir 'assets');assets" `
    (Join-Path $projectDir 'angelina_pet.py')

Write-Host "建置完成：$(Join-Path $outputDir 'Angelina桌寵.exe')"
