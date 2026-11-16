import concurrent.futures
import html
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


class DistillRequest(BaseModel):
    rawText: str
    weekNum: int = 1
    courseKey: str = "mor"
    courseName: str = "הערכת תוכניות חינוכיות"
    adminEmail: Optional[str] = None
    geminiKey: Optional[str] = None


class RerenderVideoRequest(BaseModel):
    slides: List[Dict[str, Any]]
    weekNum: int
    courseKey: str = "mor"
    courseName: str = "הערכת תוכניות חינוכיות"
    adminEmail: Optional[str] = None


class SaveSummaryRequest(BaseModel):
    summaryObj: Optional[Dict[str, Any]] = None
    deleteId: Optional[str] = None
    adminEmail: Optional[str] = None


def clean_alma_speech_errors(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = raw_text
    text = re.sub(r"קרבולכאלט|קרדו קאדו", "Cargo Cult (פולחן המטען)", text)
    text = re.sub(r"design to pinking", "Design Thinking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bStemp\b", "STEM", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPDL\b", "PBL", text)
    text = re.sub(r"גוגל טורקס", "Google Docs", text)
    text = re.sub(r"נורטבוק|נורדפרוק|לנופו", "NotebookLM", text)
    text = re.sub(r"\*\*דובר \d+:\*\*", "\n", text)
    return text.strip()


def _summarize_chunk_with_gemini(idx: int, chunk: str, course_name: str, week_num: int, api_key: str) -> str:
    prompt = f"""אתה עוזר הוראה אקדמי. לפניך מקטע #{idx + 1} מתוך תמלול שיעור {week_num} בקורס "{course_name}".
חלץ בצורה מדויקת, מרוכזת ובעברית ברורה את כל:
1. הנהלים, ההנחיות, התאריכים ודרישות ההגשה שהוזכרו במקטע זה.
2. המושגים התיאורטיים, ההגדרות, השלבים והדוגמאות מהכיתה.
3. השאלות החשובות והתובנות המעשיות.
החזר טקסט מרוכז וענייני (עד 450 מילים) בלי להמציא מידע שלא הופיע במקטע.

המקטע:
{chunk}"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    resp = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3},
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gemini chunk error [{resp.status_code}]: {resp.text[:250]}")
    data = resp.json()
    return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()


def condense_long_transcript(raw_text: str, course_name: str, week_num: int, api_key: str) -> Dict[str, Any]:
    cleaned = clean_alma_speech_errors(raw_text)
    if len(cleaned) <= 26000:
        return {"text": cleaned, "chunksUsed": 1, "originalLength": len(raw_text)}

    chunk_size = 22000
    overlap = 600
    chunks: List[str] = []
    pos = 0
    while pos < len(cleaned) and len(chunks) < 12:
        end = min(len(cleaned), pos + chunk_size)
        chunks.append(cleaned[pos:end])
        if end >= len(cleaned):
            break
        pos = end - overlap

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        summaries = list(
            pool.map(
                lambda item: _summarize_chunk_with_gemini(item[0], item[1], course_name, week_num, api_key),
                enumerate(chunks),
            )
        )

    combined = "\n\n".join(
        f"--- חלק {i + 1} מתוך {len(summaries)} ---\n{s}"
        for i, s in enumerate(summaries)
        if s
    )
    return {"text": combined[:32000], "chunksUsed": len(chunks), "originalLength": len(raw_text)}


def distill_transcript_with_gemini(condensed_text: str, week_num: int, course_name: str, api_key: str) -> Dict[str, Any]:
    prompt = f"""אתה עוזר הוראה אקדמי בתוכנית התואר השני בחינוך (מכללת בית ברל).
לפניך תמלול/מיצוי של שיעור {week_num} בקורס "{course_name}".
תקן שגיאות שמיעה פונטיות, סנן דיבורי סרק, והחזר אך ורק אובייקט JSON תקני במבנה הבא:
{{
  "title": "כותרת אקדמית ברורה לשיעור",
  "teaser": "משפט קצר ומזמין לבועית מה חדש",
  "rules": ["סעיף נוהל/הגשה 1", "סעיף 2"],
  "concepts": ["שם מושג: הסבר בהיר ודוגמה מהכיתה", "מושג 2: הסבר"],
  "steps": [
    {{"title": "שלב 1: ...", "question": "שאלה מנחה?", "desc": "הסבר קצר", "example": "דוגמה מהכיתה"}}
  ],
  "template": "תבנית טקסט מוכנה לסטודנטים להעתקה לתרגיל"
}}

התמלול:
{condensed_text[:30000]}"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    resp = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gemini distill error [{resp.status_code}]: {resp.text[:300]}")
    data = resp.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Gemini returned invalid distill JSON")
    return parsed


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
    payload = {
        "text": sanitize_hebrew_for_speech(text),
        "model_id": ELEVEN_MODEL_ID,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.85,
            "style": 0.05,
            "use_speaker_boost": True,
        },
    }
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(
                url,
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                with open(out_path, "wb") as f:
                    f.write(resp.content)
                return out_path
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                break
        except requests.RequestException as exc:
            last_err = str(exc)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"ElevenLabs turn {idx} error: {last_err}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "roshaket-podcast-engine"}


@app.get("/summaries")
def get_summaries(includeDrafts: bool = False):
    items = read_overrides()
    if not includeDrafts:
        items = [s for s in items if s.get("status") != "draft"]
    return {"summaries": items}


@app.get("/media/{filename}")
def stream_media(filename: str):
    if not re.match(r"^[A-Za-z0-9_.\-]+$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    bucket = get_bucket()
    lower = filename.lower()
    if lower.endswith(".mp4"):
        prefix = "roshaket/videos/"
        media_type = "video/mp4"
    elif lower.endswith(".png"):
        prefix = "roshaket/videos/slides/"
        media_type = "image/png"
    else:
        prefix = "roshaket/podcasts/"
        media_type = "audio/mpeg"
    blob = bucket.blob(f"{prefix}{filename}")
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Media not found")
    data = blob.download_as_bytes()
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})


@app.post("/distill-transcript")
def distill_transcript(req: DistillRequest):
    if req.adminEmail and req.adminEmail.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    raw_text = (req.rawText or "").strip()
    if len(raw_text) < 20:
        raise HTTPException(status_code=400, detail="Transcript text is too short")
    gemini_key = (req.geminiKey or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY on server")

    condensed = condense_long_transcript(raw_text, req.courseName, req.weekNum, gemini_key)
    distilled = distill_transcript_with_gemini(condensed["text"], req.weekNum, req.courseName, gemini_key)
    return {
        "ok": True,
        "distilled": distilled,
        "chunksUsed": condensed["chunksUsed"],
        "originalLength": condensed["originalLength"],
    }


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

    condensed = condense_long_transcript(req.rawText, req.courseName, req.weekNum, gemini_key)
    dialogue = generate_dialogue_with_gemini(condensed["text"], req.weekNum, req.courseName, gemini_key)

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


def build_slide_html(
    slide_idx: int,
    total_slides: int,
    slide: Dict[str, Any],
    course_name: str,
    week_num: int,
) -> str:
    badge = html.escape(str(slide.get("badge") or f"סיכום מפגש שבועי • שבוע {week_num}"))
    title = html.escape(str(slide.get("title") or ""))
    subtitle = html.escape(str(slide.get("subtitle") or course_name))
    sec1_title = html.escape(str(slide.get("sec1Title") or ""))
    sec1_body = html.escape(str(slide.get("sec1Body") or ""))
    sec2_title = html.escape(str(slide.get("sec2Title") or ""))
    sec2_body = html.escape(str(slide.get("sec2Body") or ""))
    course_hdr = html.escape(course_name)
    pct = int(((slide_idx + 1) / max(1, total_slides)) * 100)

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1080px;
    height: 1920px;
    font-family: "Noto Sans Hebrew", "Arial", sans-serif;
    background: radial-gradient(circle at 15% 20%, #e0e7ff 0%, transparent 45%),
                radial-gradient(circle at 85% 25%, #f3e8ff 0%, transparent 45%),
                radial-gradient(circle at 20% 80%, #cffafe 0%, transparent 45%),
                radial-gradient(circle at 85% 85%, #ede9fe 0%, transparent 45%),
                #f1f5f9;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    color: #0f172a;
  }}
  .top-bar {{
    background: #ffffff;
    border-bottom: 2px solid #e2e8f0;
    padding: 22px 44px;
    text-align: right;
  }}
  .top-title {{ font-size: 32px; font-weight: 800; color: #1e293b; }}
  .top-sub {{ font-size: 26px; font-weight: 500; color: #64748b; margin-top: 4px; }}
  .stage {{
    flex: 1;
    padding: 30px 42px;
    display: flex;
  }}
  .card {{
    background: rgba(255, 255, 255, 0.96);
    border: 2px solid #e2e8f0;
    border-radius: 34px;
    padding: 44px 52px;
    width: 100%;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08);
  }}
  .badge {{
    align-self: flex-start;
    background: #f3e8ff;
    border: 2px solid #c084fc;
    color: #7e22ce;
    font-size: 30px;
    font-weight: 800;
    padding: 10px 26px;
    border-radius: 999px;
    margin-bottom: 28px;
  }}
  .main-title {{
    font-size: 60px;
    font-weight: 800;
    line-height: 1.22;
    color: #0f172a;
    margin-bottom: 14px;
    unicode-bidi: plaintext;
    overflow-wrap: break-word;
  }}
  .main-sub {{
    font-size: 31px;
    color: #475569;
    font-weight: 500;
    padding-bottom: 24px;
    border-bottom: 2px solid #e2e8f0;
    margin-bottom: 34px;
    unicode-bidi: plaintext;
    overflow-wrap: break-word;
  }}
  .section {{ margin-bottom: 36px; }}
  .sec-head {{
    display: flex;
    align-items: center;
    gap: 18px;
    padding-bottom: 12px;
    margin-bottom: 16px;
  }}
  .sec1 .sec-head {{ border-bottom: 4px solid #0ea5e9; }}
  .sec2 .sec-head {{ border-bottom: 4px solid #10b981; }}
  .num {{
    width: 54px;
    height: 54px;
    border-radius: 50%;
    color: #ffffff;
    font-size: 32px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }}
  .sec1 .num {{ background: #0284c7; }}
  .sec2 .num {{ background: #059669; }}
  .sec-title {{ font-size: 38px; font-weight: 800; unicode-bidi: plaintext; overflow-wrap: break-word; }}
  .sec1 .sec-title {{ color: #0284c7; }}
  .sec2 .sec-title {{ color: #059669; }}
  .sec-body {{
    font-size: 36px;
    line-height: 1.52;
    color: #1e293b;
    font-weight: 500;
    unicode-bidi: plaintext;
    overflow-wrap: break-word;
  }}
  .footer {{
    background: #ffffff;
    border-top: 2px solid #e2e8f0;
    padding: 20px 44px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 28px;
  }}
  .footer-brand {{ color: #6d28d9; font-weight: 800; }}
  .footer-count {{ color: #475569; font-weight: 600; }}
  .prog-track {{ width: 100%; height: 12px; background: #e2e8f0; }}
  .prog-fill {{ height: 100%; width: {pct}%; background: #7c3aed; }}
</style>
</head>
<body>
  <div class="top-bar">
    <div class="top-title">ראשקט • סמסטר א' תשפ"ז • שיעור {week_num}</div>
    <div class="top-sub">{course_hdr}</div>
  </div>
  <div class="stage">
    <div class="card">
      <div class="badge">{badge}</div>
      <div class="main-title">{title}</div>
      <div class="main-sub">{subtitle}</div>
      <div class="section sec1">
        <div class="sec-head">
          <div class="num">1</div>
          <div class="sec-title">{sec1_title}</div>
        </div>
        <div class="sec-body">{sec1_body}</div>
      </div>
      <div class="section sec2">
        <div class="sec-head">
          <div class="num">2</div>
          <div class="sec-title">{sec2_title}</div>
        </div>
        <div class="sec-body">{sec2_body}</div>
      </div>
    </div>
  </div>
  <div class="footer">
    <div class="footer-brand">סיכום קולי • עופר | D-Dialog</div>
    <div class="footer-count">שקופית {slide_idx + 1} מתוך {total_slides}</div>
  </div>
  <div class="prog-track"><div class="prog-fill"></div></div>
</body>
</html>"""


def render_slides_with_chromium(
    slides: List[Dict[str, Any]],
    course_name: str,
    week_num: int,
    tmp_dir: str,
) -> List[str]:
    from playwright.sync_api import sync_playwright

    paths: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        for idx, slide in enumerate(slides):
            out_path = os.path.join(tmp_dir, f"slide_{idx:02d}.png")
            page.set_content(build_slide_html(idx, len(slides), slide, course_name, week_num), wait_until="load")
            page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
            # Auto-fit text if a slide's content overflows the card vertically
            page.evaluate("""() => {
                const card = document.querySelector('.card');
                if (!card) return;
                const bodies = document.querySelectorAll('.sec-body');
                const title = document.querySelector('.main-title');
                const sections = document.querySelectorAll('.section');
                let step = 0;
                while (card.scrollHeight > card.clientHeight + 4 && step < 4) {
                    step++;
                    bodies.forEach(b => { b.style.fontSize = (36 - step * 3) + 'px'; b.style.lineHeight = '1.42'; });
                    if (title) title.style.fontSize = (60 - step * 4) + 'px';
                    sections.forEach(s => { s.style.marginBottom = Math.max(18, 36 - step * 6) + 'px'; });
                }
            }""")
            page.screenshot(path=out_path)
            paths.append(out_path)
        browser.close()
    return paths


def generate_video_slides_with_gemini(raw_text: str, week_num: int, course_name: str, api_key: str) -> List[Dict[str, Any]]:
    prompt = f"""אתה עורך וידאו חינוכי מומחה ליצירת סרטוני סיכום קצרים (9:16 למובייל) בעברית.
לפניך תמלול/סיכום של שיעור {week_num} בקורס "{course_name}".
צור בדיוק 5 שקופיות קצרות וממוקדות (סה"כ ~75 שניות קריינות).

כללים:
1. בכל שקופית: כותרת קצרה (עד 6 מילים), תת-כותרת קצרה, 2 בלוקים ממוספרים (`sec1Title` + `sec1Body`, `sec2Title` + `sec2Body` — כל body עד 28 מילים ברורות ותכל'ס), וטקסט קריינות טבעי בעברית (`narration`, 24-34 מילים לשקופית).
2. החזר אך ורק מערך JSON תקני בפורמט:
[
  {{
    "title": "כותרת השקופית",
    "subtitle": "{course_name}",
    "sec1Title": "הרעיון המרכזי",
    "sec1Body": "הסבר תמציתי ובהיר מהשיעור.",
    "sec2Title": "השורה התחתונה המעשית",
    "sec2Body": "מה חשוב ליישם או לזכור למטלה.",
    "narration": "טקסט הקריינות המדובר לשקופית זו."
  }}
]

התמלול:
{raw_text[:28000]}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    resp = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.5},
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gemini video error [{resp.status_code}]: {resp.text[:300]}")
    data = resp.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    slides = json.loads(text)
    if not isinstance(slides, list) or len(slides) < 3:
        raise HTTPException(status_code=502, detail="Gemini returned invalid video slides")
    return slides[:5]


def _produce_video_from_slides(
    slides: List[Dict[str, Any]],
    week_num: int,
    course_key: str,
    course_name: str,
    eleven_key: str,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            audio_paths = list(
                pool.map(
                    lambda item: synthesize_turn(item[0], "OFER", item[1].get("narration", ""), eleven_key, tmp_dir),
                    enumerate(slides),
                )
            )

        png_paths = render_slides_with_chromium(slides, course_name, week_num, tmp_dir)
        segment_paths = []
        for idx, (png_path, a_path) in enumerate(zip(png_paths, audio_paths)):
            seg_path = os.path.join(tmp_dir, f"seg_{idx:02d}.mp4")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", png_path,
                    "-i", a_path,
                    "-c:v", "libx264", "-tune", "stillimage", "-r", "24",
                    "-c:a", "aac", "-b:a", "128k",
                    "-pix_fmt", "yuv420p", "-shortest",
                    seg_path,
                ],
                check=True,
                capture_output=True,
            )
            segment_paths.append(seg_path)

        concat_txt = os.path.join(tmp_dir, "vconcat.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for sp in segment_paths:
                f.write(f"file '{sp}'\n")

        raw_mp4 = os.path.join(tmp_dir, "video_voice.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", raw_mp4],
            check=True,
            capture_output=True,
        )

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", raw_mp4],
            capture_output=True,
            text=True,
        )
        dur = float(probe.stdout.strip() or "0")
        dur_label = f"{int(dur // 60)}:{int(dur % 60):02d} דק'"

        final_mp4 = os.path.join(tmp_dir, "video_final.mp4")
        if os.path.exists(AMBIENT_PATH):
            fade_out_start = max(1.0, dur - 3.0)
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", raw_mp4,
                    "-stream_loop", "-1", "-i", AMBIENT_PATH,
                    "-filter_complex",
                    f"[0:a]volume=1.0[v];[1:a]volume=0.04,afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out_start:.2f}:d=3[m];[v][m]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                    "-map", "0:v", "-map", "[aout]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    final_mp4,
                ],
                check=True,
                capture_output=True,
            )
        else:
            final_mp4 = raw_mp4

        ts = int(time.time())
        stem = f"lesson_w{week_num}_{course_key}_{ts}"
        filename = f"{stem}.mp4"
        bucket = get_bucket()
        blob = bucket.blob(f"roshaket/videos/{filename}")
        blob.cache_control = "public, max-age=31536000"
        blob.upload_from_filename(final_mp4, content_type="video/mp4")

        service_base = os.environ.get("PUBLIC_SERVICE_URL", "").rstrip("/")
        video_url = f"{service_base}/media/{filename}" if service_base else blob.public_url
        try:
            blob.make_public()
            video_url = blob.public_url
        except Exception:
            pass

        slide_urls: List[str] = []
        for idx, p_path in enumerate(png_paths):
            s_name = f"{stem}_s{idx}.png"
            s_blob = bucket.blob(f"roshaket/videos/slides/{s_name}")
            s_blob.cache_control = "public, max-age=31536000"
            s_blob.upload_from_filename(p_path, content_type="image/png")
            s_url = f"{service_base}/media/{s_name}" if service_base else s_blob.public_url
            try:
                s_blob.make_public()
                s_url = s_blob.public_url
            except Exception:
                pass
            slide_urls.append(s_url)

    return {
        "ok": True,
        "videoUrl": video_url,
        "videoDuration": dur_label,
        "slidesCount": len(slides),
        "slides": slides,
        "slideImages": slide_urls,
    }


@app.post("/generate-video")
def generate_video(req: GeneratePodcastRequest):
    if req.adminEmail and req.adminEmail.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Unauthorized")

    raw_text = (req.rawText or "").strip()
    if len(raw_text) < 40:
        raise HTTPException(status_code=400, detail="rawText is too short")

    gemini_key = (req.geminiKey or os.environ.get("GEMINI_API_KEY") or "").strip()
    eleven_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not gemini_key or not eleven_key:
        raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY or ELEVENLABS_API_KEY on server")

    condensed = condense_long_transcript(raw_text, req.courseName, req.weekNum, gemini_key)
    slides = generate_video_slides_with_gemini(condensed["text"], req.weekNum, req.courseName, gemini_key)
    return _produce_video_from_slides(slides, req.weekNum, req.courseKey, req.courseName, eleven_key)


@app.post("/rerender-video")
def rerender_video(req: RerenderVideoRequest):
    if req.adminEmail and req.adminEmail.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if not req.slides or len(req.slides) < 1:
        raise HTTPException(status_code=400, detail="slides list cannot be empty")
    eleven_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not eleven_key:
        raise HTTPException(status_code=500, detail="Missing ELEVENLABS_API_KEY on server")
    return _produce_video_from_slides(req.slides[:6], req.weekNum, req.courseKey, req.courseName, eleven_key)
