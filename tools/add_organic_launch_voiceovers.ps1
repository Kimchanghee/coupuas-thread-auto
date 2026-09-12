param(
    [string]$PackRoot = ''
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Speech

$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PackRoot)) {
    $packRoot = Join-Path $projectRoot 'output\organic-launch-pack'
}
elseif ([System.IO.Path]::IsPathRooted($PackRoot)) {
    $packRoot = $PackRoot
}
else {
    $packRoot = Join-Path $projectRoot $PackRoot
}
$audioRoot = Join-Path $packRoot '_audio'
New-Item -ItemType Directory -Force -Path $audioRoot | Out-Null

$items = @(
    @{
        Path = 'instagram\reel-01-real-demo.mp4'
        Text = '상품 링크는 있는데 글 쓰다 멈춘 적 있으시죠? 링크를 넣으면 문안 생성부터 계정별 대기열까지 이어집니다. 실제 화면으로 확인하고 매월 다섯 번 무료로 써보세요.'
    },
    @{
        Path = 'instagram\reel-02-multiaccount.mp4'
        Text = '계정이 늘어나면 어디까지 올렸는지부터 헷갈립니다. 계정마다 대기열을 따로 두고 진행 상태를 한 화면에서 확인하도록 만들었습니다.'
    },
    @{
        Path = 'tiktok\tiktok-01-which-copy.mp4'
        Text = '둘 중 어떤 글을 누르실 건가요? 제품 설명보다 상황이 먼저 나오면 궁금증이 생깁니다. 같은 상품도 네 가지로 시작합니다.'
    },
    @{
        Path = 'tiktok\tiktok-02-multiaccount.mp4'
        Text = '계정 세 개만 운영해도 어디까지 올렸는지 헷갈립니다. 그래서 계정별 대기열로 따로 관리합니다.'
    },
    @{
        Path = 'tiktok\tiktok-03-no-course.mp4'
        Text = '또 자동 수익 강의냐고요? 강의 안 팝니다. 링크를 넣고 대기열에 들어가는 실제 장면만 보여드립니다. 직접 확인하세요.'
    },
    @{
        Path = 'youtube\short-01-real-demo.mp4'
        Text = '쿠팡 상품 링크 하나가 게시 대기열까지 어떻게 이어지는지 보여드리겠습니다. 링크를 넣으면 문안과 게시 작업이 순서대로 진행됩니다.'
    },
    @{
        Path = 'youtube\short-02-four-angles.mp4'
        Text = '같은 상품도 타깃 직격, 편의 대비, 재미 반전, 사용 장면으로 다르게 시작해야 합니다. 말투만 바꾸는 게 아닙니다.'
    },
    @{
        Path = 'facebook\facebook-reel-01-explainer.mp4'
        Text = '상품 확인, 글쓰기, 계정 전환, 게시 상태 확인을 매일 반복하면 시간이 크게 듭니다. 링크를 넣으면 네 가지 문안을 만들고 계정별 대기열에서 진행 상태를 확인합니다. 수익 보장 도구가 아니라 반복 시간을 줄이는 도구입니다.'
    }
)

foreach ($item in $items) {
    $source = Join-Path $packRoot $item.Path
    $directory = Split-Path -Parent $source
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($source)
    $wav = Join-Path $audioRoot ($baseName + '.wav')
    $target = Join-Path $directory ($baseName + '-vo.mp4')

    $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $speaker.SelectVoice('Microsoft Heami Desktop')
        $speaker.Rate = 3
        $speaker.Volume = 100
        $speaker.SetOutputToWaveFile($wav)
        $speaker.Speak($item.Text)
    }
    finally {
        $speaker.Dispose()
    }

    $videoDuration = [double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $source)
    $audioDuration = [double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $wav)
    $availableDuration = [Math]::Max(1.0, $videoDuration - 0.7)
    $tempo = [Math]::Max(1.0, $audioDuration / $availableDuration)
    $tempoText = $tempo.ToString('0.000', [System.Globalization.CultureInfo]::InvariantCulture)
    $audioFilter = "[1:a]atempo=$tempoText,adelay=350|350,apad[a]"

    & ffmpeg -hide_banner -loglevel error -y -i $source -i $wav `
        -filter_complex $audioFilter `
        -map '0:v:0' -map '[a]' -c:v copy -c:a aac -b:a 160k -shortest `
        -movflags '+faststart' $target

    if ($LASTEXITCODE -ne 0) {
        throw "Voiceover mux failed: $source"
    }
}

Write-Output "Voiceovers created: $($items.Count)"
