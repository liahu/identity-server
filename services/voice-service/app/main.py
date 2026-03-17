import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Dict, List, Tuple

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


class VoiceStore:
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


class WeSpeakerEngine:
    def __init__(self, model_dir: str) -> None:
        self.model_dir = model_dir
        self.backend = self._init_backend(model_dir)

    @staticmethod
    def _init_backend(model_dir: str):
        errors: List[str] = []
        try:
            from wespeaker.cli.speaker import Speaker  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Import wespeaker failed: {e}") from e

        for kwargs in (
            {"model_dir": model_dir},
            {"model_path": model_dir},
            {"model": model_dir},
            {},
        ):
            try:
                return Speaker(**kwargs)
            except Exception as e:
                errors.append(f"{kwargs}: {e}")
        raise RuntimeError("Failed to initialize Speaker. Tried: " + " | ".join(errors))

    def extract_embedding(self, audio_path: str) -> np.ndarray:
        candidate_calls = (
            "extract_embedding",
            "compute_embedding",
            "embedding",
            "__call__",
        )
        last_error = None
        for name in candidate_calls:
            fn = getattr(self.backend, name, None)
            if fn is None:
                continue
            try:
                out = fn(audio_path)
                emb = self._to_numpy(out)
                return self._normalize(emb)
            except Exception as e:
                last_error = e
        raise RuntimeError(f"WeSpeaker embedding call failed: {last_error}")

    @staticmethod
    def _to_numpy(x) -> np.ndarray:
        if hasattr(x, "detach"):
            x = x.detach().cpu().numpy()
        elif not isinstance(x, np.ndarray):
            x = np.asarray(x, dtype=np.float32)
        if x.ndim > 1:
            x = x.reshape(-1)
        return x.astype(np.float32)

    @staticmethod
    def _normalize(x: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(x)
        if norm == 0:
            raise ValueError("Invalid voice embedding")
        return x / norm

    @staticmethod
    def cosine_score(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def save_upload_temporarily(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "upload.wav").suffix or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(upload.file.read())
            tmp_path = tmp.name
    finally:
        upload.file.close()
    if tmp_path is None:
        raise ValueError("Failed to save upload")
    return tmp_path


VOICE_DB_PATH = os.getenv("VOICE_DB_PATH", "/data/voice_embeddings.json")
WESPEAKER_MODEL_DIR = os.getenv("WESPEAKER_MODEL_DIR", "/models/wespeaker")
DEFAULT_THRESHOLD = float(os.getenv("VOICE_DEFAULT_THRESHOLD", "0.72"))

app = FastAPI(title="voice-service")
store = VoiceStore(VOICE_DB_PATH)

try:
    engine = WeSpeakerEngine(WESPEAKER_MODEL_DIR)
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
        scores = [WeSpeakerEngine.cosine_score(probe, vec) for vec in vectors]
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
    audio_path = save_upload_temporarily(file)
    try:
        emb = engine.extract_embedding(audio_path)
        count = store.add(person_id, emb)
        return {"ok": True, "person_id": person_id, "samples": count}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        Path(audio_path).unlink(missing_ok=True)


@app.post("/identify", response_model=IdentifyResponse)
def identify(file: UploadFile = File(...), threshold: float | None = Form(default=None)) -> IdentifyResponse:
    if engine is None:
        raise HTTPException(status_code=500, detail=f"Engine init failed: {init_error}")
    use_threshold = DEFAULT_THRESHOLD if threshold is None else float(threshold)
    audio_path = save_upload_temporarily(file)
    try:
        probe = engine.extract_embedding(audio_path)
        pid, score, topk = identify_top1(probe, store.all_embeddings())
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
    finally:
        Path(audio_path).unlink(missing_ok=True)


@app.post("/extract", response_model=ExtractResponse)
def extract(file: UploadFile = File(...)) -> ExtractResponse:
    if engine is None:
        raise HTTPException(status_code=500, detail=f"Engine init failed: {init_error}")
    audio_path = save_upload_temporarily(file)
    try:
        emb = engine.extract_embedding(audio_path)
        return ExtractResponse(dim=int(emb.shape[0]), preview=[float(x) for x in emb[:8]])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        Path(audio_path).unlink(missing_ok=True)
