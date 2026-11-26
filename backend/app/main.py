import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
API_URL = "https://api.data.go.kr/openapi/tn_pubr_public_cltur_fstvl_api"
DB_PATH = Path(__file__).resolve().parents[1] / "festivals.db"
PAGE_SIZE = 1000


def connect_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db() -> None:
    with connect_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS festivals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, place TEXT, start_date TEXT, end_date TEXT,
            description TEXT, organizer TEXT, host TEXT, sponsor TEXT,
            phone TEXT, homepage TEXT, road_address TEXT, lot_address TEXT,
            latitude TEXT, longitude TEXT, reference_date TEXT,
            provider_code TEXT, provider_name TEXT,
            UNIQUE(name, place, start_date, end_date, provider_code)
        )""")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(festivals)")}
        if "banner_image" not in columns:
            db.execute("ALTER TABLE festivals ADD COLUMN banner_image TEXT")
        if "banner_checked_at" not in columns:
            db.execute("ALTER TABLE festivals ADD COLUMN banner_checked_at TEXT")


class _OpenGraphImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.image = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        values = {key.lower(): value for key, value in attrs if key and value}
        key = (values.get("property") or values.get("name") or "").lower()
        if key in {"og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"}:
            self.image = values.get("content")


async def find_homepage_image(homepage: str | None) -> str | None:
    if not homepage:
        return None
    homepage = homepage.strip()
    if not homepage.startswith(("http://", "https://")):
        homepage = f"https://{homepage}"
    parsed = urlsplit(homepage)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"} or parsed.hostname.lower().endswith(".local"):
        return None
    try:
        async with httpx.AsyncClient(
            timeout=6,
            follow_redirects=True,
            headers={"User-Agent": "FestivalFieldnotes/1.0 (+public festival metadata preview)"},
        ) as client:
            response = await client.get(homepage)
            if response.status_code >= 400 or "html" not in response.headers.get("content-type", "").lower():
                return None
            parser = _OpenGraphImageParser()
            parser.feed(response.text[:1_000_000])
            if not parser.image:
                return None
            image_url = urljoin(str(response.url), parser.image.strip())
            image_parts = urlsplit(image_url)
            if image_parts.scheme not in {"http", "https"} or not image_parts.hostname:
                return None
            return image_url
    except (httpx.HTTPError, ValueError):
        return None


def find_items(payload: Any) -> tuple[list[dict], int | None]:
    """Handle the data.go.kr response envelope and minor JSON shape variations."""
    if not isinstance(payload, dict):
        raise ValueError("API 응답이 JSON 객체가 아닙니다.")
    response = payload.get("response", payload)
    header = response.get("header", {}) if isinstance(response, dict) else {}
    code = str(header.get("resultCode", ""))
    if code and code not in {"00", "0", "SUCCESS"}:
        raise ValueError(header.get("resultMsg", f"공공데이터 API 오류 ({code})"))
    body = response.get("body", {}) if isinstance(response, dict) else {}
    total = body.get("totalCount")
    total = int(total) if total not in (None, "") else None
    raw = body.get("items", [])
    if isinstance(raw, dict):
        raw = raw.get("item", [])
    if isinstance(raw, dict):
        raw = [raw]
    return ([item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []), total


async def fetch_all() -> list[dict]:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key:
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY가 설정되지 않았습니다. backend/.env를 확인하세요.")
    rows: list[dict] = []
    page = 1
    async with httpx.AsyncClient(timeout=45) as client:
        while True:
            response = await client.get(API_URL, params={
                "serviceKey": key, "pageNo": page, "numOfRows": PAGE_SIZE, "type": "json"
            })
            response.raise_for_status()
            try:
                batch, total = find_items(response.json())
            except (ValueError, TypeError) as exc:
                raise RuntimeError(f"공공데이터 API 응답을 읽지 못했습니다: {exc}") from exc
            rows.extend(batch)
            if not batch or (total is not None and len(rows) >= total) or len(batch) < PAGE_SIZE:
                break
            page += 1
    return rows


def save_all(rows: list[dict]) -> int:
    fields = {
        "name": "fstvlNm", "place": "opar", "start_date": "fstvlStartDate",
        "end_date": "fstvlEndDate", "description": "fstvlCo", "organizer": "mnnstNm",
        "host": "auspcInsttNm", "sponsor": "suprtInsttNm", "phone": "phoneNumber",
        "homepage": "homepageUrl", "road_address": "rdnmadr", "lot_address": "lnmadr",
        "latitude": "latitude", "longitude": "longitude", "reference_date": "referenceDate",
        "provider_code": "instt_code", "provider_name": "instt_nm",
    }
    columns = list(fields)
    values = [[str(row.get(src, "") or "").strip() or None for src in fields.values()] for row in rows]
    with connect_db() as db:
        db.execute("DELETE FROM festivals")
        if values:
            db.executemany(
                f"INSERT OR IGNORE INTO festivals ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                values,
            )
    return len(values)


async def sync_data() -> int:
    rows = await fetch_all()
    # The existing snapshot stays intact if fetching fails; replace only after full fetch.
    return save_all(rows)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if os.getenv("SYNC_ON_STARTUP", "true").lower() in {"1", "true", "yes"} and os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip():
        try:
            await sync_data()
        except Exception as exc:
            print(f"축제 데이터 자동 동기화 실패: {exc}")
    yield


app = FastAPI(title="전국 축제 정보 API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/festivals")
def list_festivals(page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)):
    with connect_db() as db:
        total = db.execute("SELECT COUNT(*) FROM festivals").fetchone()[0]
        records = db.execute(
            "SELECT * FROM festivals ORDER BY start_date IS NULL, start_date, name LIMIT ? OFFSET ?",
            (size, (page - 1) * size),
        ).fetchall()
    today = date.today().isoformat()
    items = []
    for row in records:
        item = dict(row)
        start, end = item["start_date"], item["end_date"]
        item["status"] = "진행중" if start and end and start <= today <= end else "완료" if end and end < today else "예정"
        items.append(item)
    return {"items": items, "total": total, "page": page, "size": size, "total_pages": (total + size - 1) // size}


@app.get("/api/festivals/{festival_id}/banner-image")
async def festival_banner_image(festival_id: int):
    with connect_db() as db:
        row = db.execute(
            "SELECT homepage, banner_image, banner_checked_at FROM festivals WHERE id = ?",
            (festival_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="축제 정보를 찾을 수 없습니다.")

    checked_at = row["banner_checked_at"]
    refresh_due = True
    if checked_at:
        try:
            checked = datetime.fromisoformat(checked_at)
            refresh_due = (datetime.now(timezone.utc) - checked).days >= 30
        except ValueError:
            pass
    if not refresh_due:
        return {"image_url": row["banner_image"]}

    image_url = await find_homepage_image(row["homepage"])
    with connect_db() as db:
        db.execute(
            "UPDATE festivals SET banner_image = ?, banner_checked_at = ? WHERE id = ?",
            (image_url, datetime.now(timezone.utc).isoformat(), festival_id),
        )
    return {"image_url": image_url}


@app.post("/api/sync")
async def sync_festivals():
    try:
        count = await sync_data()
        return {"message": "전체 축제 데이터를 동기화했습니다.", "count": count}
    except (RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
