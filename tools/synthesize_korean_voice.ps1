param(
    [Parameter(Mandatory = $true)]
    [string]$InputTextFile,

    [Parameter(Mandatory = $true)]
    [string]$OutputWav
)

$ErrorActionPreference = 'Stop'

$inputPath = [System.IO.Path]::GetFullPath($InputTextFile)
$outputPath = [System.IO.Path]::GetFullPath($OutputWav)

if (-not [System.IO.File]::Exists($inputPath)) {
    throw "Narration file not found: $inputPath"
}

$outputDirectory = [System.IO.Path]::GetDirectoryName($outputPath)
if (-not [System.IO.Directory]::Exists($outputDirectory)) {
    [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
}

Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice('Microsoft Heami Desktop')
$speaker.Rate = 0
$speaker.Volume = 100
$speaker.SetOutputToWaveFile($outputPath)

try {
    $text = [System.IO.File]::ReadAllText($inputPath, [System.Text.Encoding]::UTF8)
    $speaker.Speak($text)
}
finally {
    $speaker.SetOutputToNull()
    $speaker.Dispose()
}
