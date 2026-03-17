param(
  [string]$FaceBase = "http://localhost:18081",
  [string]$VoiceBase = "http://localhost:18082",
  [string]$FaceFile = "samples/face/obama2.jpg",
  [string]$VoiceFile = "samples/voice/jackson_1.wav",
  [double]$FaceThreshold = 0.40,
  [double]$VoiceThreshold = 0.45,
  [int]$Rounds = 5,
  [switch]$PinSingleCore,
  [int]$CpuId = 0
)

$ErrorActionPreference = "Stop"

function Invoke-IdentifyTime {
  param(
    [string]$Url,
    [string]$FilePath,
    [string]$Threshold
  )
  $resp = & curl.exe -s -o NUL -w "%{time_total}" -X POST $Url -F "file=@$FilePath" -F "threshold=$Threshold"
  return [double]$resp
}

function Get-ContainerStats {
  param([string]$Name)
  return (& docker stats --no-stream --format "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}" $Name)
}

if ($PinSingleCore) {
  & docker update --cpuset-cpus "$CpuId" face-service | Out-Null
  & docker update --cpuset-cpus "$CpuId" voice-service | Out-Null
}

$faceTimes = @()
$voiceTimes = @()

Write-Host "== Profiling Start =="
if ($PinSingleCore) {
  Write-Host "Pinned face-service and voice-service to CPU core $CpuId"
}

for ($i = 1; $i -le $Rounds; $i++) {
  $faceT = Invoke-IdentifyTime -Url "$FaceBase/identify" -FilePath $FaceFile -Threshold "$FaceThreshold"
  $voiceT = Invoke-IdentifyTime -Url "$VoiceBase/identify" -FilePath $VoiceFile -Threshold "$VoiceThreshold"
  $faceTimes += $faceT
  $voiceTimes += $voiceT

  $faceStat = Get-ContainerStats -Name "face-service"
  $voiceStat = Get-ContainerStats -Name "voice-service"
  Write-Host ("Round {0}: face={1:N3}s voice={2:N3}s" -f $i, $faceT, $voiceT)
  Write-Host ("  " + $faceStat)
  Write-Host ("  " + $voiceStat)
}

$faceAvg = ($faceTimes | Measure-Object -Average).Average
$voiceAvg = ($voiceTimes | Measure-Object -Average).Average
$faceMax = ($faceTimes | Measure-Object -Maximum).Maximum
$voiceMax = ($voiceTimes | Measure-Object -Maximum).Maximum
$faceMin = ($faceTimes | Measure-Object -Minimum).Minimum
$voiceMin = ($voiceTimes | Measure-Object -Minimum).Minimum

Write-Host "== Summary =="
Write-Host ("Face  avg={0:N3}s min={1:N3}s max={2:N3}s" -f $faceAvg, $faceMin, $faceMax)
Write-Host ("Voice avg={0:N3}s min={1:N3}s max={2:N3}s" -f $voiceAvg, $voiceMin, $voiceMax)
