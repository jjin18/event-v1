"""Hackathon Judging Platform — FastAPI backend."""
import csv
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Optional

import qrcode
import qrcode.image.svg
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

from .auth import (
    create_admin_token,
    create_judge_token,
    hash_password,
    hash_pin,
    verify_admin_token,
    verify_judge_token,
    verify_password,
)
from .database import (
    BACKUP_DIR,
    DB_PATH,
    backup_db,
    get_conn,
    init_db,
    row_to_dict,
    rows_to_list,
    start_backup_scheduler,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Hackathon Judge", version="1.0.0")

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
# Uploads live inside DATA_DIR so they persist on the Railway Volume
_DATA_DIR = Path(os.getenv("DATA_DIR", "."))
UPLOADS_DIR = _DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()
    start_backup_scheduler()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def get_judge_from_request(request: Request) -> dict:
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = verify_judge_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    with get_conn() as conn:
        judge = row_to_dict(
            conn.execute(
                "SELECT * FROM judges WHERE id=? AND is_active=1",
                (int(payload["sub"]),),
            ).fetchone()
        )
    if not judge:
        raise HTTPException(status_code=401, detail="Judge not found")
    return judge


def get_admin_from_request(request: Request) -> dict:
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = verify_admin_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return payload


def _judge_full_response(judge: dict) -> dict:
    """Return judge + all projects + all scores for their event."""
    with get_conn() as conn:
        projects = rows_to_list(
            conn.execute(
                "SELECT * FROM projects WHERE event_id=? ORDER BY CAST(table_number AS INTEGER), table_number",
                (judge["event_id"],),
            ).fetchall()
        )
        scores = rows_to_list(
            conn.execute(
                "SELECT * FROM scores WHERE judge_id=?", (judge["id"],)
            ).fetchall()
        )
        event = row_to_dict(
            conn.execute(
                "SELECT * FROM events WHERE id=?", (judge["event_id"],)
            ).fetchone()
        )
    return {
        "judge": {k: v for k, v in judge.items() if k not in ("token_hash", "pin")},
        "event": event,
        "projects": projects,
        "scores": scores,
    }


# ---------------------------------------------------------------------------
# Judge auth endpoints
# ---------------------------------------------------------------------------


class QRAuthRequest(BaseModel):
    token: str


class PINAuthRequest(BaseModel):
    pin: str
    event_id: int


@app.post("/api/judge/auth/qr")
def judge_auth_qr(body: QRAuthRequest):
    try:
        payload = verify_judge_token(body.token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid QR token")
    with get_conn() as conn:
        judge = row_to_dict(
            conn.execute(
                "SELECT * FROM judges WHERE id=? AND is_active=1",
                (int(payload["sub"]),),
            ).fetchone()
        )
    if not judge:
        raise HTTPException(status_code=401, detail="Judge not found")
    return _judge_full_response(judge)


@app.post("/api/judge/auth/pin")
def judge_auth_pin(body: PINAuthRequest):
    pin_hash = hash_pin(body.pin)
    with get_conn() as conn:
        judge = row_to_dict(
            conn.execute(
                "SELECT * FROM judges WHERE event_id=? AND pin=? AND is_active=1",
                (body.event_id, body.pin),
            ).fetchone()
        )
    if not judge:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    token = create_judge_token(judge["id"], judge["event_id"])
    result = _judge_full_response(judge)
    result["token"] = token
    return result


# ---------------------------------------------------------------------------
# Judge endpoints
# ---------------------------------------------------------------------------


@app.get("/api/judge/projects")
def judge_projects(request: Request):
    judge = get_judge_from_request(request)
    with get_conn() as conn:
        projects = rows_to_list(
            conn.execute(
                "SELECT * FROM projects WHERE event_id=? ORDER BY CAST(table_number AS INTEGER), table_number",
                (judge["event_id"],),
            ).fetchall()
        )
    return {"projects": projects}


@app.get("/api/judge/scores")
def judge_scores(request: Request):
    judge = get_judge_from_request(request)
    with get_conn() as conn:
        scores = rows_to_list(
            conn.execute(
                "SELECT * FROM scores WHERE judge_id=?", (judge["id"],)
            ).fetchall()
        )
    return {"scores": scores}


class ScoreBody(BaseModel):
    project_id: int
    innovation: float = 0
    technical: float = 0
    impact: float = 0
    presentation: float = 0
    notes: Optional[str] = ""


@app.post("/api/judge/scores")
def judge_upsert_score(body: ScoreBody, request: Request):
    judge = get_judge_from_request(request)
    total_raw = body.innovation + body.technical + body.impact + body.presentation
    total_weighted = total_raw / 4.0
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO scores
               (judge_id, project_id, innovation, technical, impact, presentation,
                total_raw, total_weighted, notes, submitted_at, updated_at, sync_status)
               VALUES (?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'),'synced')
               ON CONFLICT(judge_id, project_id) DO UPDATE SET
                 innovation=excluded.innovation,
                 technical=excluded.technical,
                 impact=excluded.impact,
                 presentation=excluded.presentation,
                 total_raw=excluded.total_raw,
                 total_weighted=excluded.total_weighted,
                 notes=excluded.notes,
                 updated_at=excluded.updated_at,
                 sync_status='synced'""",
            (
                judge["id"],
                body.project_id,
                body.innovation,
                body.technical,
                body.impact,
                body.presentation,
                total_raw,
                total_weighted,
                body.notes or "",
            ),
        )
    return {"ok": True, "total_raw": total_raw, "total_weighted": total_weighted}


# ---------------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------------


class AdminAuthBody(BaseModel):
    password: str
    event_id: Optional[int] = None


@app.post("/api/admin/auth")
def admin_auth(body: AdminAuthBody):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Wrong password")
    event_id = body.event_id or 0
    token = create_admin_token(event_id)
    return {"token": token, "event_id": event_id}


# ---------------------------------------------------------------------------
# Admin — events
# ---------------------------------------------------------------------------


@app.get("/api/admin/events")
def list_events(request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        events = rows_to_list(conn.execute("SELECT * FROM events ORDER BY id DESC").fetchall())
    for e in events:
        e.pop("admin_password_hash", None)
    return {"events": events}


class EventBody(BaseModel):
    name: str
    date: Optional[str] = ""
    venue: Optional[str] = ""
    city: Optional[str] = ""
    org_name: Optional[str] = ""
    org_address: Optional[str] = ""
    org_website: Optional[str] = ""
    organizer_name: Optional[str] = ""
    organizer_title: Optional[str] = ""
    hours_expected: Optional[float] = 4.0
    logo_path: Optional[str] = ""


@app.post("/api/admin/events")
def create_event(body: EventBody, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO events (name,date,venue,city,org_name,org_address,org_website,
               organizer_name,organizer_title,hours_expected,logo_path)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                body.name, body.date, body.venue, body.city,
                body.org_name, body.org_address, body.org_website,
                body.organizer_name, body.organizer_title,
                body.hours_expected, body.logo_path,
            ),
        )
        event_id = cur.lastrowid
        event = row_to_dict(conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())
    event.pop("admin_password_hash", None)
    return event


@app.patch("/api/admin/events/{event_id}")
def update_event(event_id: int, body: EventBody, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        conn.execute(
            """UPDATE events SET name=?,date=?,venue=?,city=?,org_name=?,org_address=?,
               org_website=?,organizer_name=?,organizer_title=?,hours_expected=?,logo_path=?
               WHERE id=?""",
            (
                body.name, body.date, body.venue, body.city,
                body.org_name, body.org_address, body.org_website,
                body.organizer_name, body.organizer_title,
                body.hours_expected, body.logo_path, event_id,
            ),
        )
        event = row_to_dict(conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())
    event.pop("admin_password_hash", None)
    return event


@app.post("/api/admin/events/{event_id}/logo")
async def upload_logo(event_id: int, file: UploadFile = File(...), request: Request = None):
    get_admin_from_request(request)
    ext = Path(file.filename).suffix.lower() or ".png"
    dest = UPLOADS_DIR / f"event_{event_id}_logo{ext}"
    content = await file.read()
    dest.write_bytes(content)
    logo_path = str(dest)
    with get_conn() as conn:
        conn.execute("UPDATE events SET logo_path=? WHERE id=?", (logo_path, event_id))
    return {"logo_path": logo_path}


@app.get("/api/uploads/{filename}")
def serve_upload(filename: str):
    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404)
    return Response(content=path.read_bytes(), media_type="image/png")


# ---------------------------------------------------------------------------
# Admin — projects
# ---------------------------------------------------------------------------


@app.get("/api/admin/projects")
def list_projects(request: Request, event_id: int = 0):
    get_admin_from_request(request)
    with get_conn() as conn:
        projects = rows_to_list(
            conn.execute(
                "SELECT * FROM projects WHERE event_id=? ORDER BY CAST(table_number AS INTEGER), table_number",
                (event_id,),
            ).fetchall()
        )
    return {"projects": projects}


class ProjectBody(BaseModel):
    event_id: int
    title: str
    team_name: Optional[str] = ""
    table_number: Optional[str] = ""
    track: Optional[str] = ""
    description: Optional[str] = ""
    devpost_url: Optional[str] = ""


@app.post("/api/admin/projects")
def create_project(body: ProjectBody, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (event_id,title,team_name,table_number,track,description,devpost_url) VALUES (?,?,?,?,?,?,?)",
            (body.event_id, body.title, body.team_name, body.table_number, body.track, body.description, body.devpost_url),
        )
        proj = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone())
    return proj


@app.patch("/api/admin/projects/{project_id}")
def update_project(project_id: int, body: ProjectBody, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET title=?,team_name=?,table_number=?,track=?,description=?,devpost_url=? WHERE id=?",
            (body.title, body.team_name, body.table_number, body.track, body.description, body.devpost_url, project_id),
        )
        proj = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
    return proj


@app.delete("/api/admin/projects/{project_id}")
def delete_project(project_id: int, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        conn.execute("DELETE FROM scores WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    return {"ok": True}


@app.post("/api/admin/projects/import")
async def import_projects(
    event_id: int,
    file: UploadFile = File(...),
    request: Request = None,
):
    get_admin_from_request(request)
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    inserted = 0
    with get_conn() as conn:
        for row in rows:
            title = row.get("title") or row.get("Title") or row.get("name") or row.get("Name") or ""
            if not title:
                continue
            conn.execute(
                "INSERT INTO projects (event_id,title,team_name,table_number,track,description,devpost_url) VALUES (?,?,?,?,?,?,?)",
                (
                    event_id,
                    title,
                    row.get("team_name") or row.get("Team Name") or row.get("team") or "",
                    row.get("table_number") or row.get("Table") or row.get("table") or "",
                    row.get("track") or row.get("Track") or "",
                    row.get("description") or row.get("Description") or row.get("tagline") or "",
                    row.get("devpost_url") or row.get("url") or row.get("URL") or row.get("Url") or "",
                ),
            )
            inserted += 1
    return {"inserted": inserted}


@app.post("/api/admin/projects/scrape")
async def scrape_projects(request: Request):
    get_admin_from_request(request)
    body = await request.json()
    url = body.get("url", "")
    event_id = body.get("event_id", 0)
    if not url:
        raise HTTPException(status_code=400, detail="url required")

    from .scrape_devpost import scrape_all

    async def generate():
        for item in scrape_all(url):
            if "error" in item:
                yield f"data: {json.dumps(item)}\n\n"
                return
            if item.get("status") == "done":
                projects = item.get("projects", [])
                with get_conn() as conn:
                    for p in projects:
                        conn.execute(
                            "INSERT INTO projects (event_id,title,team_name,table_number,track,description,devpost_url) VALUES (?,?,?,?,?,?,?)",
                            (event_id, p["title"], p["team_name"], p["table_number"], p["track"], p["description"], p["devpost_url"]),
                        )
                yield f"data: {json.dumps({'status': 'done', 'count': len(projects)})}\n\n"
            else:
                yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Admin — judges
# ---------------------------------------------------------------------------


@app.get("/api/admin/judges")
def list_judges(request: Request, event_id: int = 0):
    get_admin_from_request(request)
    with get_conn() as conn:
        judges = rows_to_list(
            conn.execute(
                "SELECT id,event_id,name,email,expertise,pin,is_active,created_at FROM judges WHERE event_id=? ORDER BY id",
                (event_id,),
            ).fetchall()
        )
    return {"judges": judges}


class JudgeBody(BaseModel):
    event_id: int
    name: str
    email: Optional[str] = ""
    expertise: Optional[str] = ""
    pin: Optional[str] = ""


def _ensure_unique_pin(conn, event_id: int, requested_pin: str = "") -> str:
    import random
    pin = requested_pin or f"{random.randint(100000,999999)}"
    existing = {r[0] for r in conn.execute("SELECT pin FROM judges WHERE event_id=?", (event_id,)).fetchall()}
    while pin in existing:
        pin = f"{random.randint(100000,999999)}"
    return pin


@app.post("/api/admin/judges")
def create_judge(body: JudgeBody, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        pin = _ensure_unique_pin(conn, body.event_id, body.pin)
        cur = conn.execute(
            "INSERT INTO judges (event_id,name,email,expertise,pin) VALUES (?,?,?,?,?)",
            (body.event_id, body.name, body.email, body.expertise, pin),
        )
        judge_id = cur.lastrowid
        token = create_judge_token(judge_id, body.event_id)
        conn.execute("UPDATE judges SET token_hash=? WHERE id=?", (token, judge_id))
        judge = row_to_dict(
            conn.execute(
                "SELECT id,event_id,name,email,expertise,pin,is_active,created_at FROM judges WHERE id=?",
                (judge_id,),
            ).fetchone()
        )
    judge["token"] = token
    return judge


@app.post("/api/admin/judges/import")
async def import_judges(event_id: int, file: UploadFile = File(...), request: Request = None):
    get_admin_from_request(request)
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    inserted = []
    with get_conn() as conn:
        for row in reader:
            name = row.get("name") or row.get("Name") or ""
            if not name:
                continue
            pin = _ensure_unique_pin(conn, event_id, row.get("pin") or row.get("PIN") or "")
            cur = conn.execute(
                "INSERT INTO judges (event_id,name,email,expertise,pin) VALUES (?,?,?,?,?)",
                (
                    event_id, name,
                    row.get("email") or row.get("Email") or "",
                    row.get("expertise") or row.get("Expertise") or "",
                    pin,
                ),
            )
            judge_id = cur.lastrowid
            token = create_judge_token(judge_id, event_id)
            conn.execute("UPDATE judges SET token_hash=? WHERE id=?", (token, judge_id))
            inserted.append({"id": judge_id, "name": name, "pin": pin, "token": token})
    return {"inserted": len(inserted), "judges": inserted}


@app.delete("/api/admin/judges/{judge_id}")
def delete_judge(judge_id: int, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        conn.execute("UPDATE judges SET is_active=0 WHERE id=?", (judge_id,))
    return {"ok": True}


@app.post("/api/admin/judges/{judge_id}/regenerate-qr")
def regenerate_qr(judge_id: int, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        judge = row_to_dict(
            conn.execute("SELECT * FROM judges WHERE id=?", (judge_id,)).fetchone()
        )
        if not judge:
            raise HTTPException(status_code=404, detail="Judge not found")
        token = create_judge_token(judge_id, judge["event_id"])
        conn.execute("UPDATE judges SET token_hash=? WHERE id=?", (token, judge_id))
    return {"token": token}


def _make_qr_image(judge: dict, event: dict, token: str) -> bytes:
    base_url = os.getenv("APP_URL", "http://localhost:5173")
    qr_url = f"{base_url}/judge?token={token}"
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    card_w, card_h = 400, 520
    card = Image.new("RGB", (card_w, card_h), "white")
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, card_w - 1, card_h - 1], outline="#333333", width=2)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_pin = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font_title = font_body = font_pin = ImageFont.load_default()

    event_name = (event or {}).get("name", "Hackathon")
    draw.text((20, 20), event_name, fill="#111111", font=font_title)

    qr_size = 240
    qr_resized = qr_img.resize((qr_size, qr_size))
    card.paste(qr_resized, ((card_w - qr_size) // 2, 60))

    draw.text((20, 320), f"Judge: {judge['name']}", fill="#222222", font=font_body)
    draw.text((20, 348), f"Backup PIN: {judge['pin']}", fill="#444444", font=font_pin)
    draw.text((20, 380), "Scan to begin judging →", fill="#666666", font=font_body)

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    return buf.getvalue()


@app.get("/api/admin/judges/{judge_id}/qr")
def judge_qr(judge_id: int, request: Request):
    get_admin_from_request(request)
    with get_conn() as conn:
        judge = row_to_dict(
            conn.execute("SELECT * FROM judges WHERE id=?", (judge_id,)).fetchone()
        )
        if not judge:
            raise HTTPException(status_code=404, detail="Judge not found")
        event = row_to_dict(
            conn.execute("SELECT * FROM events WHERE id=?", (judge["event_id"],)).fetchone()
        )
    token = judge.get("token_hash") or create_judge_token(judge_id, judge["event_id"])
    png_bytes = _make_qr_image(judge, event, token)
    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/admin/qr/zip")
def all_qr_zip(request: Request, event_id: int = 0):
    get_admin_from_request(request)
    with get_conn() as conn:
        judges = rows_to_list(
            conn.execute(
                "SELECT * FROM judges WHERE event_id=? AND is_active=1", (event_id,)
            ).fetchall()
        )
        event = row_to_dict(
            conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for judge in judges:
            token = judge.get("token_hash") or create_judge_token(judge["id"], event_id)
            png_bytes = _make_qr_image(judge, event, token)
            zf.writestr(f"qr_{judge['name'].replace(' ','_')}.png", png_bytes)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=judge_qr_codes.zip"},
    )


# ---------------------------------------------------------------------------
# Admin — leaderboard + exports
# ---------------------------------------------------------------------------


@app.get("/api/admin/leaderboard")
def leaderboard(request: Request, event_id: int = 0):
    get_admin_from_request(request)
    with get_conn() as conn:
        rows = rows_to_list(
            conn.execute(
                """SELECT p.id, p.title, p.team_name, p.table_number, p.track,
                          AVG(s.total_weighted) as avg_score,
                          COUNT(DISTINCT s.judge_id) as judge_count,
                          MIN(s.total_weighted) as min_score,
                          MAX(s.total_weighted) as max_score
                   FROM projects p
                   LEFT JOIN scores s ON s.project_id = p.id
                   WHERE p.event_id=?
                   GROUP BY p.id
                   ORDER BY avg_score DESC NULLS LAST""",
                (event_id,),
            ).fetchall()
        )
    return {"leaderboard": rows}


@app.get("/api/admin/export/scores")
def export_scores_csv(request: Request, event_id: int = 0):
    get_admin_from_request(request)
    with get_conn() as conn:
        rows = rows_to_list(
            conn.execute(
                """SELECT j.name as judge_name, p.title, p.team_name, p.table_number,
                          s.innovation, s.technical, s.impact, s.presentation,
                          s.total_raw, s.total_weighted, s.notes, s.updated_at
                   FROM scores s
                   JOIN judges j ON j.id=s.judge_id
                   JOIN projects p ON p.id=s.project_id
                   WHERE p.event_id=?
                   ORDER BY p.table_number, j.name""",
                (event_id,),
            ).fetchall()
        )
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scores.csv"},
    )


@app.get("/api/admin/export/leaderboard")
def export_leaderboard_csv(request: Request, event_id: int = 0):
    get_admin_from_request(request)
    with get_conn() as conn:
        rows = rows_to_list(
            conn.execute(
                """SELECT p.table_number, p.title, p.team_name, p.track,
                          ROUND(AVG(s.total_weighted),3) as avg_score,
                          COUNT(DISTINCT s.judge_id) as judge_count
                   FROM projects p
                   LEFT JOIN scores s ON s.project_id = p.id
                   WHERE p.event_id=?
                   GROUP BY p.id
                   ORDER BY avg_score DESC NULLS LAST""",
                (event_id,),
            ).fetchall()
        )
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leaderboard.csv"},
    )


@app.get("/api/admin/export/luma")
def export_luma_csv(request: Request, event_id: int = 0, top: int = 10):
    get_admin_from_request(request)
    with get_conn() as conn:
        rows = rows_to_list(
            conn.execute(
                """SELECT p.title as name, p.team_name, p.devpost_url,
                          ROUND(AVG(s.total_weighted),3) as score
                   FROM projects p
                   LEFT JOIN scores s ON s.project_id = p.id
                   WHERE p.event_id=?
                   GROUP BY p.id
                   ORDER BY score DESC NULLS LAST
                   LIMIT ?""",
                (event_id, top),
            ).fetchall()
        )
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=luma_winners.csv"},
    )


@app.get("/api/admin/export/letters")
def export_letters_zip(request: Request, event_id: int = 0):
    """Return a ZIP of per-judge score summaries as CSV (letters are generated client-side as PDF)."""
    get_admin_from_request(request)
    with get_conn() as conn:
        judges = rows_to_list(
            conn.execute(
                "SELECT id, name, expertise FROM judges WHERE event_id=? AND is_active=1", (event_id,)
            ).fetchall()
        )
        event = row_to_dict(conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for judge in judges:
            with get_conn() as conn:
                scores = rows_to_list(
                    conn.execute(
                        """SELECT p.title, p.team_name, p.table_number,
                                  s.total_weighted, s.innovation, s.technical, s.impact, s.presentation
                           FROM scores s JOIN projects p ON p.id=s.project_id
                           WHERE s.judge_id=?
                           ORDER BY p.table_number""",
                        (judge["id"],),
                    ).fetchall()
                )
            csv_buf = io.StringIO()
            csv_buf.write(f"Judge: {judge['name']}\n")
            csv_buf.write(f"Event: {(event or {}).get('name','')}\n\n")
            if scores:
                writer = csv.DictWriter(csv_buf, fieldnames=list(scores[0].keys()))
                writer.writeheader()
                writer.writerows(scores)
            zf.writestr(f"scores_{judge['name'].replace(' ','_')}.csv", csv_buf.getvalue())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=judge_letters.zip"},
    )


# ---------------------------------------------------------------------------
# Health + static file serving
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/admin/backup")
def trigger_backup(request: Request):
    get_admin_from_request(request)
    backup_db()
    backups = sorted(BACKUP_DIR.glob("scores_*.db"))
    return {"ok": True, "backups": [str(b.name) for b in backups]}


# Serve React frontend for all non-API routes
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return Response(content=index.read_text(), media_type="text/html")
        return Response(content="Frontend not built", status_code=503)
