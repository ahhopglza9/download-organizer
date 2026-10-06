# 다운로드 정리 설치 스크립트. DownloadOrganizer-Setup.cmd가 받아서 실행합니다.
# 테스트용: -Root 다른폴더 -SourceZip 소스.zip -NoShortcuts -NoRegister -NoLaunch
param(
    [string]$Root = (Join-Path $env:LOCALAPPDATA 'DownloadOrganizer'),
    [string]$SourceZip = '',
    [switch]$NoShortcuts,
    [switch]$NoRegister,
    [switch]$NoLaunch
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = 'ahhopglza9/download-organizer'
$UvVersion = '0.12.23'
$UvSha256 = '75d05de6762778c31ee183398de7dd15093fad0ed90b1f236d8205ea5ec00c90'
$WebView2Id = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
$AppName = '다운로드 정리'
$Headers = @{ 'User-Agent' = 'download-organizer' }

function Step($n, $text) { Write-Host ''; Write-Host "[$n/7] $text" -ForegroundColor Cyan }

function Test-WebView2 {
    foreach ($k in @("HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$WebView2Id",
                     "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$WebView2Id",
                     "HKCU:\Software\Microsoft\EdgeUpdate\Clients\$WebView2Id")) {
        $pv = (Get-ItemProperty -Path $k -Name pv -ErrorAction SilentlyContinue).pv
        if ($pv -and $pv -ne '0.0.0.0') { return $true }
    }
    return $false
}

function Test-Under($path, $parent) {
    if (-not $path) { return $false }
    $p = [IO.Path]::GetFullPath($path); $q = [IO.Path]::GetFullPath($parent).TrimEnd('\')
    return $p.Equals($q, [StringComparison]::OrdinalIgnoreCase) -or $p.StartsWith($q + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Stop-Running {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { Test-Under $_.ExecutablePath $Root } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

function New-Shortcut($path, $target, $arguments, $workdir, $icon) {
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
    $s.TargetPath = $target
    $s.Arguments = $arguments
    $s.WorkingDirectory = $workdir
    $s.IconLocation = "$icon,0"
    $s.Description = '다운로드한 파일을 원하는 폴더로 옮겨 줍니다'
    $s.Save()
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root 'data') | Out-Null
$log = Join-Path $Root 'data\설치기록.txt'
Start-Transcript -Path $log -Append | Out-Null
$tmp = Join-Path $env:TEMP ('do-install-' + [guid]::NewGuid())
try {
    Write-Host "$AppName 설치를 시작해요. 설치 위치: $Root"

    Step 1 '컴퓨터 확인'
    if (-not [Environment]::Is64BitOperatingSystem -or [Environment]::OSVersion.Version.Major -lt 10) {
        throw '64비트 Windows 10 이상에서만 쓸 수 있어요.'
    }
    if (-not (Test-WebView2)) {
        Start-Process 'https://developer.microsoft.com/microsoft-edge/webview2/#download-section'
        throw '화면을 그리는 데 필요한 Microsoft Edge WebView2가 없어요. 방금 열린 페이지에서 "Evergreen Bootstrapper"를 받아 설치한 뒤, 이 설치를 다시 실행해 주세요.'
    }

    Step 2 '켜져 있는 프로그램 끄기'
    Stop-Running

    Step 3 '설치 도구(uv) 받기'
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $uvZip = Join-Path $tmp 'uv.zip'
    Invoke-WebRequest -UseBasicParsing "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip" -OutFile $uvZip
    $hash = (Get-FileHash -Algorithm SHA256 $uvZip).Hash.ToLower()
    if ($hash -ne $UvSha256) { throw "받은 설치 도구가 원본과 달라요. 인터넷 연결을 확인하고 다시 시도해 주세요. ($hash)" }
    Expand-Archive -Path $uvZip -DestinationPath (Join-Path $tmp 'uv') -Force
    Copy-Item (Join-Path $tmp 'uv\uv.exe') (Join-Path $Root 'uv.exe') -Force

    Step 4 '프로그램 받기'
    $appZip = Join-Path $tmp 'app.zip'
    if ($SourceZip) {
        Copy-Item $SourceZip $appZip
    } else {
        $tag = (Invoke-RestMethod -UseBasicParsing "https://api.github.com/repos/$Repo/releases/latest" -Headers $Headers).tag_name
        Invoke-WebRequest -UseBasicParsing "https://github.com/$Repo/archive/refs/tags/$tag.zip" -OutFile $appZip
    }
    # 설치 폴더 안에서 풀어야 임시 폴더가 다른 드라이브에 있어도 옮기기가 실패하지 않습니다.
    $staging = Join-Path $Root 'app.staging'
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
    Expand-Archive -Path $appZip -DestinationPath $staging -Force
    $inner = Get-ChildItem $staging -Directory | Select-Object -First 1
    $app = Join-Path $Root 'app'
    if (Test-Path $app) { Remove-Item $app -Recurse -Force }
    Move-Item $inner.FullName $app
    Remove-Item $staging -Recurse -Force

    Step 5 'Python과 라이브러리 설치 (1분 정도 걸려요)'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $Root 'python'
    $env:UV_CACHE_DIR = Join-Path $Root 'cache'
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $Root '.venv'
    $env:UV_PYTHON_PREFERENCE = 'only-managed'
    & (Join-Path $Root 'uv.exe') sync --frozen --no-dev --project $app
    if ($LASTEXITCODE -ne 0) { throw "라이브러리를 설치하지 못했어요. (uv 종료 코드 $LASTEXITCODE)" }
    Copy-Item (Join-Path $app 'launcher.py') (Join-Path $Root 'launcher.py') -Force
    Copy-Item (Join-Path $app 'installer\uninstall.ps1') (Join-Path $Root 'uninstall.ps1') -Force
    Copy-Item (Join-Path $app 'installer\uninstall.cmd') (Join-Path $Root '제거.cmd') -Force

    $pythonw = Join-Path $Root '.venv\Scripts\pythonw.exe'
    $launcher = Join-Path $Root 'launcher.py'
    $icon = Join-Path $app 'ui\icon.ico'

    Step 6 '바로가기 만들고 앱 목록에 등록'
    if (-not $NoShortcuts) {
        New-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk") $pythonw "`"$launcher`"" $Root $icon
        New-Shortcut (Join-Path ([Environment]::GetFolderPath('Programs')) "$AppName.lnk") $pythonw "`"$launcher`"" $Root $icon
    }
    if (-not $NoRegister) {
        $key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DownloadOrganizer'
        $version = (Select-String -Path (Join-Path $app 'pyproject.toml') -Pattern '^version\s*=\s*"(.+)"').Matches[0].Groups[1].Value
        New-Item -Path $key -Force | Out-Null
        Set-ItemProperty -Path $key -Name DisplayName -Value $AppName
        Set-ItemProperty -Path $key -Name DisplayVersion -Value $version
        Set-ItemProperty -Path $key -Name Publisher -Value 'ahhopglza9'
        Set-ItemProperty -Path $key -Name DisplayIcon -Value $icon
        Set-ItemProperty -Path $key -Name InstallLocation -Value $Root
        Set-ItemProperty -Path $key -Name UninstallString -Value "`"$(Join-Path $Root '제거.cmd')`""
        Set-ItemProperty -Path $key -Name NoModify -Value 1 -Type DWord
        Set-ItemProperty -Path $key -Name NoRepair -Value 1 -Type DWord
    }

    Step 7 '실행'
    if (-not $NoLaunch) { Start-Process -FilePath $pythonw -ArgumentList "`"$launcher`"" -WorkingDirectory $Root }
    Write-Host ''
    Write-Host '설치를 마쳤어요. 잠시 뒤 "어느 폴더에서 찾을까요?" 화면이 떠요.' -ForegroundColor Green
    Stop-Transcript | Out-Null
    if (-not $NoLaunch) { Start-Sleep -Seconds 4 }
}
catch {
    Write-Host ''
    Write-Host "설치하지 못했어요: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "자세한 기록: $log"
    Stop-Transcript | Out-Null
    if (-not $NoLaunch) { Read-Host '엔터를 누르면 창이 닫혀요' }
    exit 1
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
