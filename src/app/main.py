from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

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

# 4. pydantic 모델 정의

class TourismSpot(BaseModel):
    id: str # 고유 ID
    name: str # place name
    category: str # cluster
    lat: float # 위도
    lng: float # 경도
    visitors_monthly: int # 월별 방문자 수
    tmap_search_rank: int # TMAP 검색 순위
    bus_interval_min: int # 버스 배차 간격 (분)
    tii_score: float # TII 점수
    cei_score: float # CEI 점수
    status: str # 상태 (isolated, normal, hub 등)
    description: str # 설명 (선택 사항)
    
# 거제시 실제 데이터 기반 샘플 데이터셋 (나중에 data/에서 로드)
SPOTS_DATA = [
    {
        "id": "gohyeon_terminal",
        "name": "고현버스터미널 (도심 거점)",
        "category": "hub",
        "lat": 34.8893,
        "lng": 128.6225,
        "visitors_monthly": 185000,
        "tmap_search_rank": 1,
        "bus_interval_min": 10,
        "tii_score": 0.12,
        "cei_score": 0.55,
        "status": "hub",
        "description": "거제도 교통의 출발점. 시외버스 터미널 및 중심 상권 밀집."
    },
    {
        "id": "wind_hill",
        "name": "바람의 언덕 / 신선대 (남부면)",
        "category": "attraction",
        "lat": 34.7618,
        "lng": 128.6247,
        "visitors_monthly": 92000,
        "tmap_search_rank": 2,
        "bus_interval_min": 110,
        "tii_score": 0.88,
        "cei_score": 0.42,
        "status": "isolated",
        "description": "Tmap 검색 2위 대표 명소이나, 시내버스 배차 110분으로 극심한 교통 고립지."
    },
    {
        "id": "maemi_castle",
        "name": "매미성 (장목면)",
        "category": "attraction",
        "lat": 34.9818,
        "lng": 128.7186,
        "visitors_monthly": 78000,
        "tmap_search_rank": 3,
        "bus_interval_min": 85,
        "tii_score": 0.74,
        "cei_score": 0.48,
        "status": "isolated",
        "description": "젊은 층 인기 포토스팟. 외곽 해안가에 위치해 대중교통 접근성 취약."
    },
    {
        "id": "gujora_beach",
        "name": "구조라 해수욕장 / 샛바람소리길 (일운면)",
        "category": "attraction",
        "lat": 34.8118,
        "lng": 128.6836,
        "visitors_monthly": 45000,
        "tmap_search_rank": 6,
        "bus_interval_min": 60,
        "tii_score": 0.58,
        "cei_score": 0.61,
        "status": "normal",
        "description": "해양 레저 및 로컬 골목길이 공존하는 잠재 앵커 스팟."
    }
]    
    
# 5. 메인 화면 렌더링 라우터
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

# 새로 추가 6. 거제시 관광 거점 데이터 목록 반환 API
@app.get("/api/spots", response_model = List[TourismSpot])
async def get_spots():
    """
    거제시 관광지 데이터 목록 반환 API
    """
    return SPOTS_DATA

# 5. 헬스체크 API 엔드포인트
@app.get("/api/health")
async def health_check():
    """
    헬스체크 API 엔드포인트
    """
    return {"status": "ok", "message": "Local Synergy Maker API is running."}