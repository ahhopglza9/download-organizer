# 다운로드 정리 제거 스크립트. 설치 폴더의 제거.cmd가 임시 폴더로 복사해서 실행합니다.
# 이 설치 폴더를 가리키는 등록·바로가기만 지웁니다 (다른 위치의 복사본은 건드리지 않음).
param(
    [string]$Root = (Join-Path $env:LOCALAPPDATA 'DownloadOrganizer'),
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$AppName = '다운로드 정리'
$rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\')

function Test-Under($path) {
    if (-not $path) { return $false }
    $p = [IO.Path]::GetFullPath($path)
    return $p.Equals($rootFull, [StringComparison]::OrdinalIgnoreCase) -or $p.StartsWith($rootFull + '\', [StringComparison]::OrdinalIgnoreCase)
}

# 설치 폴더가 맞는지 먼저 확인합니다. 제거.cmd가 다른 곳(예: 바탕화면)으로 복사돼 실행돼도 그 폴더를 지우지 않게.
$looksInstalled = (Test-Path (Join-Path $rootFull 'launcher.py')) -and (Test-Path (Join-Path $rootFull 'uv.exe')) -and
                  (Test-Path (Join-Path $rootFull 'app\main.py')) -and (Test-Path (Join-Path $rootFull '.venv'))
if (-not $looksInstalled) {
    Write-Host "이 폴더는 $AppName 설치 폴더가 아니라서 아무것도 지우지 않았어요: $rootFull" -ForegroundColor Red
    Write-Host '설정 → 앱 → 설치된 앱에서 "다운로드 정리"를 찾아 제거해 주세요.'
    if (-not $Force) { Read-Host '엔터를 누르면 창이 닫혀요' }
    exit 1
}

if (-not $Force) {
    $answer = Read-Host "$AppName 을(를) 지울까요? 설정과 고른 폴더 기억도 함께 지워져요. (Y/N)"
    if ($answer -notmatch '^[Yy]') { Write-Host '지우지 않았어요.'; Start-Sleep -Seconds 2; exit 0 }
}

Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { Test-Under $_.ExecutablePath } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$value = (Get-ItemProperty -Path $run -Name DownloadOrganizer -ErrorAction SilentlyContinue).DownloadOrganizer
if ($value -and $value.ToLower().Contains($rootFull.ToLower())) { Remove-ItemProperty -Path $run -Name DownloadOrganizer }

$shell = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $lnk = Join-Path $dir "$AppName.lnk"
    if ((Test-Path $lnk) -and (Test-Under $shell.CreateShortcut($lnk).TargetPath)) { Remove-Item $lnk -Force }
}

$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DownloadOrganizer'
$location = (Get-ItemProperty -Path $key -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation
if (Test-Under $location) { Remove-Item -Path $key -Recurse -Force }

if (Test-Path -LiteralPath $rootFull) { Remove-Item -LiteralPath $rootFull -Recurse -Force }
Write-Host "$AppName 을(를) 지웠어요."
if (-not $Force) { Start-Sleep -Seconds 2 }
