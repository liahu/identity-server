import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Dict, List, Tuple

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel


class MatchItem(BaseModel):
    person_id: str
    score: float


class IdentifyResponse(BaseModel):
    matched: bool
    person_id: str | None
    score: float | None
    threshold: float
    topk: List[MatchItem]


class ExtractResponse(BaseModel):
    dim: int
    preview: List[float]


class FaceStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self._save({})

    def _load(self) -> Dict[str, List[List[float]]]:
        with self.lock:
            with self.db_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                return data

    def _save(self, data: Dict[str, List[List[float]]]) -> None:
        with self.lock:
            with self.db_path.open("w", encoding="utf-8") as f:
                json.dump(data, f)

    def add(self, person_id: str, embedding: np.ndarray) -> int:
        data = self._load()
        if person_id not in data:
            data[person_id] = []
        data[person_id].append(embedding.astype(float).tolist())
        self._save(data)
        return len(data[person_id])

    def all_embeddings(self) -> Dict[str, List[np.ndarray]]:
        raw = self._load()
        out: Dict[str, List[np.ndarray]] = {}
        for pid, items in raw.items():
            out[pid] = [np.asarray(x, dtype=np.float32) for x in items]
        return out


class SFaceEngine:
    def __init__(self, detector_path: str, recognizer_path: str) -> None:
        if not Path(detector_path).exists():
            raise FileNotFoundError(f"YuNet model not found: {detector_path}")
        if not Path(recognizer_path).exists():
            raise FileNotFoundError(f"SFace model not found: {recognizer_path}")
        self.detector = cv2.FaceDetectorYN.create(
            model=detector_path,
            config="",
            input_size=(320, 320),
            score_threshold=0.8,
            nms_threshold=0.3,
            top_k=5000,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")

    def extract_embedding(self, image_bgr: np.ndarray) -> np.ndarray:
        h, w = image_bgr.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(image_bgr)
        if faces is None or len(faces) == 0:
            raise ValueError("No face detected")
        if len(faces) > 1:
            raise ValueError("Multiple faces detected")
        aligned = self.recognizer.alignCrop(image_bgr, faces[0])
        embedding = self.recognizer.feature(aligned)
        norm = np.linalg.norm(embedding)
        if norm == 0:
            raise ValueError("Invalid embedding")
        return (embedding / norm).flatten()

    @staticmethod
    def cosine_score(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def read_uploaded_image(upload: UploadFile) -> np.ndarray:
    suffix = Path(upload.filename or "upload.jpg").suffix or ".jpg"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(upload.file.read())
            tmp_path = tmp.name
        img = cv2.imread(tmp_path)
        if img is None:
            raise ValueError("Failed to decode image")
        return img
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)
        upload.file.close()


DETECTOR_PATH = os.getenv("YUNET_MODEL_PATH", "/models/face_detection_yunet_2023mar.onnx")
MODEL_PATH = os.getenv("SFACE_MODEL_PATH", "/models/face_recognition_sface_2021dec.onnx")
DB_PATH = os.getenv("FACE_DB_PATH", "/data/face_embeddings.json")
DEFAULT_THRESHOLD = float(os.getenv("FACE_DEFAULT_THRESHOLD", "0.40"))

app = FastAPI(title="face-service")
store = FaceStore(DB_PATH)

try:
    engine = SFaceEngine(DETECTOR_PATH, MODEL_PATH)
except Exception as e:
    engine = None
    init_error = str(e)
else:
    init_error = ""


def identify_top1(probe: np.ndarray, gallery: Dict[str, List[np.ndarray]]) -> Tuple[str | None, float | None, List[MatchItem]]:
    scored: List[MatchItem] = []
    for person_id, vectors in gallery.items():
        if not vectors:
            continue
        scores = [SFaceEngine.cosine_score(probe, vec) for vec in vectors]
        best = max(scores)
        scored.append(MatchItem(person_id=person_id, score=best))
    scored.sort(key=lambda x: x.score, reverse=True)
    if not scored:
        return None, None, []
    top = scored[0]
    return top.person_id, top.score, scored[:3]


@app.get("/health")
def health() -> dict:
    return {"ok": engine is not None, "error": init_error}


@app.post("/enroll")
def enroll(person_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    if engine is None:
        raise HTTPException(status_code=500, detail=f"Engine init failed: {init_error}")
    try:
        img = read_uploaded_image(file)
        emb = engine.extract_embedding(img)
        count = store.add(person_id, emb)
        return {"ok": True, "person_id": person_id, "samples": count}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/identify", response_model=IdentifyResponse)
def identify(
    file: UploadFile = File(...),
    threshold: float | None = Form(default=None),
    userids: str | None = Form(default=None)
) -> IdentifyResponse:
    if engine is None:
        raise HTTPException(status_code=500, detail=f"Engine init failed: {init_error}")
    use_threshold = DEFAULT_THRESHOLD if threshold is None else float(threshold)
    try:
        img = read_uploaded_image(file)
        probe = engine.extract_embedding(img)

        all_embeddings = store.all_embeddings()
        if userids:
            target_ids = [uid.strip() for uid in userids.split(',') if uid.strip()]
            filtered_embeddings = {pid: all_embeddings[pid] for pid in target_ids if pid in all_embeddings}
        else:
            filtered_embeddings = all_embeddings

        pid, score, topk = identify_top1(probe, filtered_embeddings)
        matched = bool(score is not None and score >= use_threshold)
        return IdentifyResponse(
            matched=matched,
            person_id=pid if matched else None,
            score=score,
            threshold=use_threshold,
            topk=topk,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/extract", response_model=ExtractResponse)
def extract(file: UploadFile = File(...)) -> ExtractResponse:
    if engine is None:
        raise HTTPException(status_code=500, detail=f"Engine init failed: {init_error}")
    try:
        img = read_uploaded_image(file)
        emb = engine.extract_embedding(img)
        return ExtractResponse(dim=int(emb.shape[0]), preview=[float(x) for x in emb[:8]])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
