from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
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

# 7. 헬스체크 API 엔드포인트
@app.get("/api/health")
async def health_check():
    """
    헬스체크 API 엔드포인트
    """
    return {"status": "ok", "message": "Local Synergy Maker API is running."}

# 8. 시뮬레이션 요청 & 응답 Pydantic 모델 정의
class SimulationRequest(BaseModel):
    target_spot_id: str # 목적지 ID
    shuttle_count: int # 투입할 셔틀버스 대수 (1~5)
    
class SimulationResponse(BaseModel):
    spot_name: str           # 대상 관광지 이름
    origin_name: str         # 출발지 (고현버스터미널)
    origin_coords: List[float]  # 출발지 좌표 [lat, lng]
    target_coords: List[float]  # 목적지 좌표 [lat, lng]
    shuttle_count: int       # 투입 대수
    original_interval_min: int  # 기존 버스 배차간격 (분)
    new_interval_min: int    # 신규 셔틀 배차간격 (분)
    time_saved_percent: float # 대기시간 단축률 (%)
    expected_new_visitors: int # 예상 추가 유입 관광객 수 (월간)
    carbon_reduction_kg: float # 예상 탄소 저감량 (kg)
    synergy_summary: str     # 정책 요약 리포트

# 9. 스마트 셔틀 시뮬레이션 계산 POST API
@app.post("/api/simulate", response_model = SimulationResponse)
async def run_simulation(req: SimulationRequest):
    """
    셔틀버스 투입 대수에 따른 배차간격 단축 및 기대효과를 계산하는 시뮬레이터 API
    """
    # 1. 출발지 및 대상 목적지 데이터 찾기
    hub_spot = next(s for s in SPOTS_DATA if s["id"] == "gohyeon_terminal")
    target_spot = next((s for s in SPOTS_DATA if s["id"] == req.target_spot_id), None)
    
    if not target_spot:
        raise HTTPException(status_code=404, detail="Target spot not found.")
    
    # 2. 시뮬레이션 수식 계산
    orig_interval = target_spot["bus_interval_min"]
    shuttle_count = max(1, req.shuttle_count)
    
    # 셔틀 투입에 따른 신규 배차간격 계산 (기본 편도 35분 기준 왕복 70분 / 셔틀 대수)
    round_trip_min = 70
    new_interval = max(15, round(round_trip_min / shuttle_count))
    
    # 배차 대기시간 단축률 (%)
    time_saved_percent = round(((orig_interval - new_interval) / orig_interval) * 100, 1)
    
    # 외곽지 추가 유입 관광객 추정치 (단축률과 TII 고립도 비례)
    base_visitors = target_spot["visitors_monthly"]
    expected_new_visitors = int(base_visitors * (time_saved_percent / 100) * 0.35)
    
    # 자가용 분산에 따른 탄소 저감량 (승용차 1대당 약 2.5kg 탄소 절감 추정)
    reduced_cars = int(expected_new_visitors * 0.4)  # 40%가 자가용 이용 가정
    carbon_reduction_kg = round(reduced_cars * 2.5, 1)
    
    # 정책 요약 코멘트 
    
    summary = (
        f"[{target_spot['name']}]에 주말 관광 셔틀 {shuttle_count}대 투입 시, "
        f"배차간격이 {orig_interval}분에서 {new_interval}분으로 {time_saved_percent}% 단축되며, "
        f"월간 약 {expected_new_visitors:,}명의 뚜벅이 관광객 추가 유입이 기대됩니다."
    )
    return SimulationResponse(
        spot_name=target_spot["name"],
        origin_name=hub_spot["name"],
        origin_coords=[hub_spot["lat"], hub_spot["lng"]],
        target_coords=[target_spot["lat"], target_spot["lng"]],
        shuttle_count=shuttle_count,
        original_interval_min=orig_interval,
        new_interval_min=new_interval,
        time_saved_percent=time_saved_percent,
        expected_new_visitors=expected_new_visitors,
        carbon_reduction_kg=carbon_reduction_kg,
        synergy_summary=summary
    )
    