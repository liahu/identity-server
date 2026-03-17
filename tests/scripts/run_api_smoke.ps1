param(
  [string]$FaceBase = "http://localhost:18081",
  [string]$VoiceBase = "http://localhost:18082",
  [double]$FaceThreshold = 0.40,
  [double]$VoiceThreshold = 0.72
)

$ErrorActionPreference = "Stop"

function Post-Multipart {
  param(
    [string]$Url,
    [string]$FilePath,
    [hashtable]$Form
  )
  $args = @("-s", "-X", "POST", $Url, "-F", "file=@$FilePath")
  foreach ($k in $Form.Keys) {
    $args += @("-F", "$k=$($Form[$k])")
  }
  $raw = & curl.exe @args
  if (-not $raw) { return $null }
  return ($raw | ConvertFrom-Json)
}

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$faceDir = Join-Path $root "samples\face"
$voiceDir = Join-Path $root "samples\voice"

$obama = Join-Path $faceDir "obama.jpg"
$obama2 = Join-Path $faceDir "obama2.jpg"
$biden = Join-Path $faceDir "biden.jpg"

$jackson0 = Join-Path $voiceDir "jackson_0.wav"
$jackson1 = Join-Path $voiceDir "jackson_1.wav"
$nicolas0 = Join-Path $voiceDir "nicolas_0.wav"

Write-Host "=== Face Enroll ==="
$r1 = Post-Multipart -Url "$FaceBase/enroll" -FilePath $obama -Form @{ person_id = "face_obama" }
$r2 = Post-Multipart -Url "$FaceBase/enroll" -FilePath $biden -Form @{ person_id = "face_biden" }
$r1 | ConvertTo-Json -Depth 8
$r2 | ConvertTo-Json -Depth 8

Write-Host "=== Face Identify (obama2) ==="
$r3 = Post-Multipart -Url "$FaceBase/identify" -FilePath $obama2 -Form @{ threshold = "$FaceThreshold" }
$r3 | ConvertTo-Json -Depth 8

Write-Host "=== Voice Enroll ==="
$v1 = Post-Multipart -Url "$VoiceBase/enroll" -FilePath $jackson0 -Form @{ person_id = "voice_jackson" }
$v2 = Post-Multipart -Url "$VoiceBase/enroll" -FilePath $nicolas0 -Form @{ person_id = "voice_nicolas" }
$v1 | ConvertTo-Json -Depth 8
$v2 | ConvertTo-Json -Depth 8

Write-Host "=== Voice Identify (jackson_1) ==="
$v3 = Post-Multipart -Url "$VoiceBase/identify" -FilePath $jackson1 -Form @{ threshold = "$VoiceThreshold" }
$v3 | ConvertTo-Json -Depth 8

Write-Host "=== Summary ==="
Write-Host ("Face matched:  " + $r3.matched + " person=" + $r3.person_id + " score=" + $r3.score)
Write-Host ("Voice matched: " + $v3.matched + " person=" + $v3.person_id + " score=" + $v3.score)
