# identity-server (Docker Compose)

## Services
- `face-service`: OpenCV YuNet + SFace face recognition API.
- `voice-service`: WeSpeaker speaker recognition API.
- `gradio-ui`: Browser test console (upload + webcam + microphone).

## Quick Start
1. Put face models:
   - `services/face-service/models/face_detection_yunet_2023mar.onnx`
   - `services/face-service/models/face_recognition_sface_2021dec.onnx`
2. Put WeSpeaker model assets under:
   - `services/voice-service/models/wespeaker/`
3. Build and start services:
   - `docker compose up --build`
4. Health checks:
   - Face: `http://localhost:18081/health`
   - Voice: `http://localhost:18082/health`
5. Gradio UI:
   - `http://localhost:17860`

## Feature Storage
- Face embeddings are persisted in `data/face/face_embeddings.json`
- Voice embeddings are persisted in `data/voice/voice_embeddings.json`

## Test Script
Run integration tests with Docker Compose:
- `docker compose run --rm tester --help`

The script supports enrolling and identifying for both services.

Example:
`docker compose run --rm tester --face-enroll-a /samples/alice_1.jpg --face-enroll-b /samples/bob_1.jpg --face-probe /samples/alice_2.jpg --voice-enroll-a /samples/alice_1.wav --voice-enroll-b /samples/bob_1.wav --voice-probe /samples/alice_2.wav`

## API
- `GET /health`
- `POST /extract` (`file`, returns feature dim + preview)
- `POST /enroll` (`person_id` + `file`)
- `POST /identify` (`file` + optional `threshold`)

Identify response:
```json
{
  "matched": true,
  "person_id": "u001",
  "score": 0.78,
  "threshold": 0.7,
  "topk": [
    {"person_id": "u001", "score": 0.78}
  ]
}
```
python test_services.py --face-enroll-a /samples/face/obama.jpg --face-enroll-b /samples/face/obama2.jpg --face-probe /samples/face/biden.jpg

 python test_services.py  --voice-enroll-a /samples/voice/jackson_0.wav --voice-enroll-b /samples/voice/jackson_1.wav --voice-probe  /samples/voice/nicolas_0.wav 


docker-compose run  --entrypoint bash  tester