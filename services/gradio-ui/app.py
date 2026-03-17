import json
import os
from pathlib import Path
from typing import Any

import gradio as gr
import requests
from gradio_client import utils as gr_client_utils


FACE_URL = os.getenv("FACE_SERVICE_URL", "http://face-service:8080")
VOICE_URL = os.getenv("VOICE_SERVICE_URL", "http://voice-service:8080")
DEFAULT_FACE_THRESHOLD = float(os.getenv("UI_FACE_THRESHOLD", "0.40"))
DEFAULT_VOICE_THRESHOLD = float(os.getenv("UI_VOICE_THRESHOLD", "0.72"))


_orig_get_type = gr_client_utils.get_type
_orig_json_schema_to_python_type = gr_client_utils._json_schema_to_python_type


def _patched_get_type(schema: Any) -> str:
    # Work around gradio_client schema parsing when additionalProperties is boolean.
    if isinstance(schema, bool):
        return "Any"
    return _orig_get_type(schema)


gr_client_utils.get_type = _patched_get_type


def _patched_json_schema_to_python_type(schema: Any, defs: Any = None) -> str:
    if isinstance(schema, bool):
        return "Any"
    return _orig_json_schema_to_python_type(schema, defs)


gr_client_utils._json_schema_to_python_type = _patched_json_schema_to_python_type


def _post_file(url: str, file_path: str, form: dict[str, Any] | None = None) -> dict[str, Any]:
    with open(file_path, "rb") as f:
        files = {"file": (Path(file_path).name, f)}
        resp = requests.post(url, files=files, data=form or {}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _extract_face(file_path: str | None) -> str:
    if not file_path:
        return "请先上传/拍摄人脸图片。"
    try:
        data = _post_file(f"{FACE_URL}/extract", file_path)
        return f"face dim={data['dim']}, preview={data['preview']}"
    except Exception as e:
        return f"人脸特征提取失败: {e}"


def _extract_voice(file_path: str | None) -> str:
    if not file_path:
        return "请先上传/录制音频。"
    try:
        data = _post_file(f"{VOICE_URL}/extract", file_path)
        return f"voice dim={data['dim']}, preview={data['preview']}"
    except Exception as e:
        return f"声纹特征提取失败: {e}"


def _enroll_face(person_id: str, file_path: str | None) -> str:
    if not person_id.strip():
        return "请输入 person_id。"
    if not file_path:
        return "请先上传/拍摄人脸图片。"
    try:
        data = _post_file(f"{FACE_URL}/enroll", file_path, {"person_id": person_id.strip()})
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return f"人脸入库失败: {e}"


def _enroll_voice(person_id: str, file_path: str | None) -> str:
    if not person_id.strip():
        return "请输入 person_id。"
    if not file_path:
        return "请先上传/录制音频。"
    try:
        data = _post_file(f"{VOICE_URL}/enroll", file_path, {"person_id": person_id.strip()})
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return f"声纹入库失败: {e}"


def _status_indicator(matched: bool, label: str) -> str:
    color = "#0b8f31" if matched else "#b12a2a"
    text = "已识别" if matched else "陌生人/未通过"
    return (
        "<div style='display:flex;align-items:center;gap:10px;padding:8px 0;'>"
        f"<div style='width:14px;height:14px;border-radius:50%;background:{color};'></div>"
        f"<div style='font-weight:600'>{text} - {label}</div>"
        "</div>"
    )


def _identify(face_path: str | None, voice_path: str | None, face_thr: float, voice_thr: float) -> tuple[str, str]:
    result: dict[str, Any] = {"face": None, "voice": None, "final": None}
    face_match = None
    voice_match = None

    if face_path:
        try:
            face_data = _post_file(f"{FACE_URL}/identify", face_path, {"threshold": str(face_thr)})
            result["face"] = face_data
            face_match = face_data["person_id"] if face_data.get("matched") else None
        except Exception as e:
            result["face"] = {"error": str(e)}

    if voice_path:
        try:
            voice_data = _post_file(f"{VOICE_URL}/identify", voice_path, {"threshold": str(voice_thr)})
            result["voice"] = voice_data
            voice_match = voice_data["person_id"] if voice_data.get("matched") else None
        except Exception as e:
            result["voice"] = {"error": str(e)}

    if face_match and voice_match and face_match == voice_match:
        final_label = face_match
        matched = True
    elif face_match and not voice_path:
        final_label = face_match
        matched = True
    elif voice_match and not face_path:
        final_label = voice_match
        matched = True
    else:
        final_label = "unknown"
        matched = False

    result["final"] = {"matched": matched, "person_id": final_label}
    indicator = _status_indicator(matched, final_label)
    return indicator, json.dumps(result, ensure_ascii=False, indent=2)


with gr.Blocks(title="Identity Test Console") as demo:
    gr.Markdown(
        "# Identity Test Console\n"
        "- 支持上传与 webcam/microphone 采样\n"
        "- 先提特征（extract），再入库（enroll）\n"
        "- 识别区支持人脸+声纹联合判断"
    )

    with gr.Tab("注册/入库"):
        person_id = gr.Textbox(label="person_id", placeholder="例如 user_001")
        with gr.Row():
            face_upload = gr.Image(
                label="人脸图片（上传或 webcam）",
                type="filepath",
                sources=["upload", "webcam"],
            )
            voice_upload = gr.Audio(
                label="声纹音频（上传或 microphone）",
                type="filepath",
                sources=["upload", "microphone"],
            )

        with gr.Row():
            face_extract_btn = gr.Button("3) 人脸算特征")
            face_store_btn = gr.Button("5) 人脸特征入库")
        face_log = gr.Textbox(label="人脸结果", lines=5)

        with gr.Row():
            voice_extract_btn = gr.Button("4) 声纹算特征")
            voice_store_btn = gr.Button("5) 声纹特征入库")
        voice_log = gr.Textbox(label="声纹结果", lines=5)

        face_extract_btn.click(fn=_extract_face, inputs=[face_upload], outputs=[face_log])
        face_store_btn.click(fn=_enroll_face, inputs=[person_id, face_upload], outputs=[face_log])
        voice_extract_btn.click(fn=_extract_voice, inputs=[voice_upload], outputs=[voice_log])
        voice_store_btn.click(fn=_enroll_voice, inputs=[person_id, voice_upload], outputs=[voice_log])

    with gr.Tab("识别测试"):
        with gr.Row():
            face_probe = gr.Image(
                label="6) Webcam/上传 图片测试",
                type="filepath",
                sources=["upload", "webcam"],
            )
            voice_probe = gr.Audio(
                label="6) 麦克风/上传 音频测试",
                type="filepath",
                sources=["upload", "microphone"],
            )
        with gr.Row():
            face_thr = gr.Slider(0.0, 1.0, value=DEFAULT_FACE_THRESHOLD, step=0.01, label="Face Threshold")
            voice_thr = gr.Slider(0.0, 1.0, value=DEFAULT_VOICE_THRESHOLD, step=0.01, label="Voice Threshold")
        identify_btn = gr.Button("开始识别")
        indicator = gr.HTML(label="8) 指示器")
        details = gr.Code(label="7) 识别详情", language="json")
        identify_btn.click(
            fn=_identify,
            inputs=[face_probe, voice_probe, face_thr, voice_thr],
            outputs=[indicator, details],
        )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, show_api=False, share=True)
