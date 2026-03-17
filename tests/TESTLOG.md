# Test Log

## 2026-03-09

### Environment
- Stack: `docker compose` (`face-service`, `voice-service`, `gradio-ui`)
- Host CPU target: Intel i7-13700K (single-core pin profiling script prepared)

### Health Check
- `GET /health` face: `{"ok":true,"error":""}`
- `GET /health` voice: `{"ok":true,"error":""}`

### Sample Assets
- Face samples (low resolution): `samples/face/{obama.jpg, obama2.jpg, biden.jpg}`
- Voice samples (16kHz mono): `samples/voice/{jackson_0.wav, jackson_1.wav, nicolas_0.wav}`

### DB Snapshot
- Face:
  - `face_obama=3`
  - `face_biden=3`
- Voice:
  - `voice_jackson=3`
  - `voice_nicolas=3`

### Smoke Test Summary
- Face identify (`obama2.jpg`, threshold `0.40`):
  - matched `true`
  - top1 `face_obama`
  - score `~0.76`
- Voice identify (`jackson_1.wav`):
  - threshold `0.72` => matched `false` (score `~0.476`)
  - threshold `0.45` => matched `true`

### Profiling Snapshot (3 rounds)
- Script: `tests/scripts/profile_api.ps1`
- Face identify latency:
  - avg `0.026s`, min `0.020s`, max `0.031s`
  - container memory `~251 MiB`
- Voice identify latency:
  - avg `0.066s`, min `0.037s`, max `0.091s`
  - container memory `~605 MiB`

### Notes
- Threshold definition: request is accepted as match only if `cosine_score >= threshold`.
- Use `-PinSingleCore -CpuId <n>` in profiling script for single-core constrained runs.
