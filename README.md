# 전국 축제 아카이브

공공데이터포털의 [전국문화축제표준데이터](https://www.data.go.kr/data/15013104/standard.do)를 수집해 SQLite에 저장하고, React 화면에서 페이지당 10개씩 보여주는 서비스입니다.

## 기술 구성

- 프론트엔드: React + Vite
- 백엔드: FastAPI
- 데이터베이스: SQLite (`backend/festivals.db`, 실행 시 생성)
- 원천 API: `https://api.data.go.kr/openapi/tn_pubr_public_cltur_fstvl_api`

원천 API는 JSON 응답의 `pageNo`, `numOfRows`(최대 1,000)를 사용합니다. 백엔드는 전체 페이지를 모두 받은 다음에 DB 스냅샷을 교체합니다. 화면 조회는 원천 API를 호출하지 않고 SQLite에서 합니다.

## 실행 방법 (Windows PowerShell)

### 1. API 키 설정

공공데이터포털에서 전국문화축제표준데이터 OpenAPI 활용 신청 후 일반 인증키(Decoding)를 발급받습니다. 프로젝트 루트에서:

```powershell
Copy-Item backend/.env.example backend/.env
notepad backend/.env
```

`DATA_GO_KR_SERVICE_KEY=` 뒤에 발급 키를 붙여넣고 저장합니다. `.env` 파일은 공개 저장소에 올리지 마세요.

### 2. 백엔드 실행

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

처음 실행할 때 키가 설정돼 있으면 전국 데이터를 모두 수집하여 `backend/festivals.db`에 저장합니다. 자동 수집을 끄려면 `backend/.env`에 `SYNC_ON_STARTUP=false`를 설정하세요. 수동 전체 동기화는 `POST http://127.0.0.1:8000/api/sync` 또는 FastAPI 문서(`/docs`)에서 실행할 수 있습니다.

> `requirements.txt`를 찾을 수 없다는 오류가 나면 백엔드 폴더로 이동했는지 확인하세요. 파일 위치는 `backend/requirements.txt`입니다.

### 3. 프론트엔드 실행

새 PowerShell 창에서 프로젝트 루트로 이동한 뒤:

```powershell
cd frontend
npm install
npm run dev
```

터미널에 표시된 Vite 주소(기본값 `http://localhost:5173`)를 브라우저에서 엽니다. 프론트엔드는 개발 프록시를 통해 FastAPI(`http://127.0.0.1:8000`)에 연결됩니다.

## API

- `GET /api/festivals?page=1&size=10`: SQLite 축제 목록과 페이지 정보 반환
- `POST /api/sync`: 원천 API의 전체 페이지를 수집한 뒤 SQLite 스냅샷 갱신

축제 상태는 시작일과 종료일을 기준으로 `예정`, `진행중`, `완료`로 계산합니다. 날짜가 비어 있는 경우 `예정`으로 표시됩니다.
