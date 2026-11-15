import concurrent.futures
import json
import os
import re
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from pydantic import BaseModel

app = FastAPI(title="Roshaket Podcast Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BUCKET_NAME = os.environ.get("GCS_BUCKET", "d-dialog-hub.firebasestorage.app")
OVERRIDES_BLOB = "roshaket/summaries_overrides.json"
OFER_VOICE_ID = os.environ.get("ELEVEN_VOICE_OFER", "IXZoL6GLiwH62df6VBtq")
HOST_VOICE_ID = os.environ.get("ELEVEN_VOICE_HOST", "EXAVITQu4vr4xnSDxMaL")
ELEVEN_MODEL_ID = os.environ.get("ELEVEN_MODEL", "eleven_v4")
AMBIENT_PATH = os.path.join(os.path.dirname(__file__), "ambient_soft_bg.wav")
ADMIN_EMAILS = {"saritofer.k@gmail.com", "ofer@ddialog.co.il"}


class GeneratePodcastRequest(BaseModel):
    rawText: str
    weekNum: int
    courseKey: str = "mor"
    courseName: str = "הערכת תוכניות חינוכיות"
    summaryId: Optional[str] = None
    adminEmail: Optional[str] = None
    geminiKey: Optional[str] = None
    summaryObj: Optional[Dict[str, Any]] = None


class SaveSummaryRequest(BaseModel):
    summaryObj: Optional[Dict[str, Any]] = None
    deleteId: Optional[str] = None
    adminEmail: Optional[str] = None


def sanitize_hebrew_for_speech(text: str) -> str:
    text = text.replace("ראשקט", "ראש שקט")
    text = re.sub(r"https?://\S+", "", text)
    text = text.replace("Moodle", "מודל").replace("moodle", "מודל")
    text = text.replace("PDF", "פי די אף")
    text = text.replace("Sunk Cost", "סאנק קוסט")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_bucket():
    client = storage.Client()
    return client.bucket(BUCKET_NAME)


def read_overrides() -> List[Dict[str, Any]]:
    try:
        bucket = get_bucket()
        blob = bucket.blob(OVERRIDES_BLOB)
        if not blob.exists():
            return []
        data = json.loads(blob.download_as_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_overrides(items: List[Dict[str, Any]]) -> None:
    bucket = get_bucket()
    blob = bucket.blob(OVERRIDES_BLOB)
    blob.cache_control = "no-cache, max-age=0"
    blob.upload_from_string(
        json.dumps(items, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )


def generate_dialogue_with_gemini(raw_text: str, week_num: int, course_name: str, api_key: str) -> List[Dict[str, str]]:
    prompt = f"""אתה עורך פודקאסטים אקדמי-יזמי בעברית.
לפניך תמלול/סיכום של שיעור {week_num} בקורס "{course_name}".
הפק תסריט פודקאסט חי, טבעי וזורם באורך של כ-5 דקות דיבור (בין 26 ל-30 תורות שיחה קצרים, כ-680 עד 760 מילים סה"כ).

הדוברים:
- HOST (נועה): שותפה ללמידה מהכיתה. שואלת שאלות חדות וטבעיות, מבקשת הבהרות ומייצגת את הסטודנטים.
- OFER (עופר): עונה בגובה העיניים, בטון רגוע, חד ומעשי, מחבר לתיאוריה ולמשימות בפועל.

כללים חשובים:
1. שמור על משפטים קצרים וטבעיים לדיבור בעברית (בלי סלנג מוגזם ובלי טון קרייני רשמי).
2. כתוב מספרים ותאריכים במילים כשהם חלק משיחה (למשל "ארבע", "עשרה אחוז", "חמישה עשר בנובמבר") ובלי ראשי תיבות באנגלית שיישמעו מוזר ב-TTS.
3. התמקד בתובנות המרכזיות, במושגים התיאורטיים, בדוגמאות מהשיעור ובמשימות התכלס לשבוע הקרוב.
4. החזר אך ורק מערך JSON תקני בפורמט:
[
  {{"speaker": "HOST", "text": "..."}},
  {{"speaker": "OFER", "text": "..."}}
]

התמלול:
{raw_text[:32000]}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    resp = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gemini error [{resp.status_code}]: {resp.text[:300]}")

    data = resp.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    dialogue = json.loads(text)
    if not isinstance(dialogue, list) or len(dialogue) < 6:
        raise HTTPException(status_code=502, detail="Gemini returned invalid dialogue structure")
    return dialogue


def synthesize_turn(idx: int, speaker: str, text: str, api_key: str, tmp_dir: str) -> str:
    voice_id = OFER_VOICE_ID if speaker.upper() == "OFER" else HOST_VOICE_ID
    out_path = os.path.join(tmp_dir, f"turn_{idx:02d}.mp3")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    resp = requests.post(
        url,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": sanitize_hebrew_for_speech(text),
            "model_id": ELEVEN_MODEL_ID,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.85,
                "style": 0.05,
                "use_speaker_boost": True,
            },
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs turn {idx} error [{resp.status_code}]: {resp.text[:200]}")
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path


@app.get("/health")
def health():
    return {"status": "ok", "service": "roshaket-podcast-engine"}


@app.get("/summaries")
def get_summaries():
    return {"summaries": read_overrides()}


@app.get("/media/{filename}")
def stream_media(filename: str):
    if not re.match(r"^[A-Za-z0-9_.\-]+$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    bucket = get_bucket()
    blob = bucket.blob(f"roshaket/podcasts/{filename}")
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    data = blob.download_as_bytes()
    return Response(content=data, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.post("/save-summary")
def save_summary(req: SaveSummaryRequest):
    if req.adminEmail and req.adminEmail.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    items = read_overrides()
    if req.deleteId:
        items = [x for x in items if x.get("id") != req.deleteId]
    if req.summaryObj and req.summaryObj.get("id"):
        sid = req.summaryObj["id"]
        items = [x for x in items if x.get("id") != sid]
        items.append(req.summaryObj)
    write_overrides(items)
    return {"ok": True, "count": len(items)}


@app.post("/generate-podcast")
def generate_podcast(req: GeneratePodcastRequest):
    if req.adminEmail and req.adminEmail.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Unauthorized")

    gemini_key = os.environ.get("GEMINI_API_KEY") or req.geminiKey
    eleven_key = os.environ.get("ELEVENLABS_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=400, detail="Missing GEMINI_API_KEY")
    if not eleven_key:
        raise HTTPException(status_code=500, detail="Missing ELEVENLABS_API_KEY on server")
    if not req.rawText or len(req.rawText.strip()) < 40:
        raise HTTPException(status_code=400, detail="Transcript text is too short")

    dialogue = generate_dialogue_with_gemini(req.rawText, req.weekNum, req.courseName, gemini_key)

    with tempfile.TemporaryDirectory() as tmp_dir:
        silence_mp3 = os.path.join(tmp_dir, "silence_250ms.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.25", "-c:a", "libmp3lame", "-b:a", "128k", silence_mp3],
            check=True,
            capture_output=True,
        )

        turn_paths: List[Optional[str]] = [None] * len(dialogue)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(synthesize_turn, i, item["speaker"], item["text"], eleven_key, tmp_dir): i
                for i, item in enumerate(dialogue)
            }
            for fut in concurrent.futures.as_completed(futures):
                idx = futures[fut]
                turn_paths[idx] = fut.result()

        concat_lines = []
        for i, p in enumerate(turn_paths):
            concat_lines.append(f"file '{p}'")
            if i < len(turn_paths) - 1:
                concat_lines.append(f"file '{silence_mp3}'")

        concat_txt = os.path.join(tmp_dir, "concat.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(concat_lines))

        voice_only = os.path.join(tmp_dir, "voice_only.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c:a", "libmp3lame", "-b:a", "128k", voice_only],
            check=True,
            capture_output=True,
        )

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", voice_only],
            capture_output=True,
            text=True,
        )
        dur = float(probe.stdout.strip() or "0")
        dur_label = f"{int(dur // 60)}:{int(dur % 60):02d} דק'"

        final_mp3 = os.path.join(tmp_dir, "podcast_final.mp3")
        if os.path.exists(AMBIENT_PATH):
            fade_out_start = max(1.0, dur - 4.0)
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", voice_only,
                    "-stream_loop", "-1", "-i", AMBIENT_PATH,
                    "-filter_complex",
                    f"[0:a]volume=1.0[v];[1:a]volume=0.045,afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start:.2f}:d=4[m];[v][m]amix=inputs=2:duration=first:dropout_transition=2[out]",
                    "-map", "[out]",
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    final_mp3,
                ],
                check=True,
                capture_output=True,
            )
        else:
            final_mp3 = voice_only

        ts = int(time.time())
        filename = f"lesson_w{req.weekNum}_{req.courseKey}_{ts}.mp3"
        bucket = get_bucket()
        blob = bucket.blob(f"roshaket/podcasts/{filename}")
        blob.cache_control = "public, max-age=31536000"
        blob.upload_from_filename(final_mp3, content_type="audio/mpeg")

        service_base = os.environ.get("PUBLIC_SERVICE_URL", "").rstrip("/")
        audio_url = f"{service_base}/media/{filename}" if service_base else blob.public_url
        try:
            blob.make_public()
            audio_url = blob.public_url
        except Exception:
            pass

        updated_summary = None
        if req.summaryObj:
            updated_summary = dict(req.summaryObj)
            updated_summary["audioUrl"] = audio_url
            updated_summary["audioTitle"] = "פודקאסט סיכום המפגש (שיחה דו-קולית)"
            updated_summary["audioDuration"] = dur_label
            items = read_overrides()
            sid = updated_summary.get("id")
            if sid:
                items = [x for x in items if x.get("id") != sid]
                items.append(updated_summary)
                write_overrides(items)

    return {
        "ok": True,
        "audioUrl": audio_url,
        "audioDuration": dur_label,
        "turnsCount": len(dialogue),
        "summary": updated_summary,
    }
