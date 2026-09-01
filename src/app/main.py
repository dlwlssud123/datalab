from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 1. api 앱 인스턴스 생성
app = FastAPI(
    title = "Local Synergy Maker API",
    description = "관광지 교통 고립지 분석 및 상권 다양성 시뮬레이터",
    version = "1.0.0"
)

# 2. 파일 경로 설정
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory = str(BASE_DIR / "templates"))

# 3. 정적 파일 서빙 마운트
app.mount("/static", StaticFiles(directory = str(BASE_DIR / "static")), name = "static")

# 4. 메인 화면 렌더링 라우터
@app.get("/")
async def read_root(request: Request):
    """
    브라우저로 접속 시 index.html 화면을 렌더링하여 반환
    """
    return templates.TemplateResponse(
        request = request,
        name = "index.html",
        context = {
            "title": "Local Synergy Maker"
        }
    )

# 5. 헬스체크 API 엔드포인트
@app.get("/api/health")
async def health_check():
    """
    헬스체크 API 엔드포인트
    """
    return {"status": "ok", "message": "Local Synergy Maker API is running."}