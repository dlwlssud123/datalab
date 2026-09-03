import json
import pandas as pd
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, List, Optional

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
    bus_routes_count: Optional[int] = None
    bus_stop_basis: Optional[str] = None
    observed_runs_count: Optional[int] = None
    avg_gap_min: Optional[float] = None
    max_gap_min: Optional[float] = None
    first_bus_time: Optional[str] = None
    last_bus_time: Optional[str] = None
    bus_route_numbers: Optional[str] = None
    bus_schedule_source: Optional[str] = None
    bus_schedule_note: Optional[str] = None
    walk_distance_m: Optional[int] = None
    tii_demand_pressure: Optional[float] = None
    bus_frequency_per_hour: Optional[float] = None
    last_mile_access_index: Optional[float] = None
    tii_supply_index: Optional[float] = None
    tii_raw_score: Optional[float] = None
    tii_log_score: Optional[float] = None
    tii_formula_basis: Optional[str] = None
    
PROCESSED_CSV_PATH = BASE_DIR.parent.parent / "data" / "processed" / "geoje_real_spots.csv"
   
def load_processed_spots():
    """
    전처리된 관광지 데이터를 로드하여 딕셔너리 리스트로 변환
    """
    if PROCESSED_CSV_PATH.exists():
        df = pd.read_csv(PROCESSED_CSV_PATH)
        df = df.astype(object).where(pd.notna(df), None)
        return df.to_dict(orient="records")
    else:
        print(f"Warning: Processed CSV file not found at {PROCESSED_CSV_PATH}. Returning empty list.")
        return []
    
SPOTS_DATA = load_processed_spots()
    
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
    return load_processed_spots()

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
    data_basis: Dict[str, str] # 데이터 근거 (TII, CEI, 배차간격 등)

# 9. 스마트 셔틀 시뮬레이션 계산 POST API
@app.post("/api/simulate", response_model = SimulationResponse)
async def run_simulation(req: SimulationRequest):
    """
    셔틀버스 투입 대수에 따른 배차간격 단축 및 기대효과를 계산하는 시뮬레이터 API
    """
    # 1. 출발지 및 대상 목적지 데이터 찾기
    spots = load_processed_spots()
    hub_spot = next(s for s in spots if s["id"] == "gohyeon_terminal")
    target_spot = next((s for s in spots if s["id"] == req.target_spot_id), None)
    
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
        synergy_summary=summary,
        data_basis = {
            "original_interval_min": "기준지표: 전처리 CSV에 저장된 관광지별 버스 배차간격",
            "new_interval_min": "정책 시나리오: 왕복 70분을 셔틀 대수로 나누고 최소 15분으로 제한",
            "time_saved_percent": "시나리오 계산값: 기준 배차 대비 신규 배차 감소율",
            "expected_new_visitors": "추정값: 기준 방문자 규모 × 대기시간 단축률 × 0.35",
            "carbon_reduction_kg": "추정값: 추가 유입객 중 40% 자가용 대체, 대체 1건당 2.5kg 감축 가정",
        }
    )
    
# 🌟 [새로 추가] 10. 상권 다양성 시뮬레이션 요청 & 응답 모델
class CommercialSimRequest(BaseModel):
    target_town: str         # 대상 지역 (예: '남부면', '장목면')
    store_category: str      # 입점 지원 업종 ('local_fnb', 'craft_shop', 'culture_book', 'franchise_copy')
    new_store_count: int     # 입점 점포 수 (1~5개)
    
class CommercialSimResponse(BaseModel):
    town_name: str           # 지역명
    selected_category_name: str # 선택한 업종명
    original_cei: float      # 기존 CEI
    simulated_cei: float     # 시뮬레이션 후 CEI
    cei_change_percent: float # 다양성 증감율 (%)
    expected_stay_increase_min: int # 머신러닝 예측 체류시간 증가 (분)
    vacant_resolved_count: int # 해소된 공실 수
    policy_recommendation: str # 지자체 정책 제언
    ml_formula: str          # 적용된 머신러닝 회귀 수식
    data_basis: Dict[str, str] # 데이터 근거 (TII, CEI, 배차간격 등)

# 머신러닝 회귀 가중치 로드
WEIGHTS_PATH = BASE_DIR.parent / "analysis" / "regression_weights.json"
ML_WEIGHTS = {}
if WEIGHTS_PATH.exists():
    try:
        with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
            ML_WEIGHTS = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load regression weights: {e}")

# 11. 상권 다양성 시뮬레이터 POST API (머신러닝 회귀식 결합)
@app.post("/api/simulate-commercial", response_model = CommercialSimResponse)
async def run_commercial_simulation(req: CommercialSimRequest):
    """
    공실 상가에 로컬 특화 업종 입점 시 상권 엔트로피 및 체류시간 변화를 머신러닝(NumPy Ridge)으로 시뮬레이션
    """
    town_base_cei = {
        "남부면": 0.65,  # 바람의 언덕 (숙박/한식 과밀)
        "장목면": 0.64,  # 매미성
        "동부면": 0.63,  # 몽돌해변
        "고현동": 0.77   # 도심
    }
    
    orig_cei = town_base_cei.get(req.target_town, 0.65)
    store_count = max(1, req.new_store_count)
    
    category_meta = {
        "local_fnb": ("로컬 특산물 F&B (거제 유자/해산물 타파스 등)", 0.05, 0.02),
        "craft_shop": ("청년 해양 공방 & 로컬 굿즈 편집숍", 0.06, 0.03),
        "culture_book": ("독립 서점 & 로컬 복합 문화공간", 0.07, 0.04),
        "franchise_copy": ("전국 복제 프랜차이즈 / 무인 사진관", -0.03, 0.0)
    }
    
    cat_name, entropy_weight, vacancy_drop_rate = category_meta.get(
        req.store_category, ("기타 로컬 숍", 0.03, 0.01)
    )
    
    # 신규 cei 계산 (결핍 업종은 상승, 복제 업종은 하락)
    delta_cei = entropy_weight * store_count
    sim_cei = round(max(0.40, min(0.95, orig_cei + delta_cei)), 2)
    cei_change_pct = round(((sim_cei - orig_cei) / orig_cei) * 100, 1)
    
    # 🎯 머신러닝(Ridge Regression) 기반 체류시간 증가분 산출
    # ΔStay = (2.13 × ΔInterval) + (411.8 × ΔCEI) + (121.9 × ΔVacancy) + Intercept
    b_interval = ML_WEIGHTS.get("coef_interval", 2.13)
    b_cei = ML_WEIGHTS.get("coef_cei", 411.8)
    b_vac = ML_WEIGHTS.get("coef_vacancy", 121.9)
    intercept = ML_WEIGHTS.get("intercept", 10.06)
    
    # 상권 단독 기여분: ΔCEI와 공실 해소 기여분 반영
    if req.store_category == "franchise_copy":
        stay_increase = 0
    else:
        # 다양성 상승(ΔCEI)과 공실률 개선(ΔVacancy)에 따른 순수 체류 증가량
        predicted_min = (b_cei * max(0, delta_cei)) + (b_vac * (vacancy_drop_rate * store_count)) + (intercept * 0.5)
        stay_increase = int(round(predicted_min))

    formula_str = ML_WEIGHTS.get("formula", "ΔStay = 2.13*ΔInterval + 411.8*ΔCEI + 121.9*ΔVacancy + 10.06")
    
    # 지자체 정책 권고사항 도출
    if req.store_category == "franchise_copy":
        policy_msg = (
            f"⚠️ [경고] {req.target_town}에 유행성 복제 매장 {store_count}개소 추가 시, "
            f"상권 획일화가 {abs(cei_change_pct)}% 심화되어 로컬 고유 매력이 퇴색됩니다. 입점 제한 및 지원 배제를 권고합니다."
        )
    else:
        policy_msg = (
            f"✅ [권고] {req.target_town}에 '{cat_name}' {store_count}개소 입점 지원 시, "
            f"상권 다양성(CEI)이 {cei_change_pct}% 향상되며 머신러닝 예측 결과 체류시간이 약 +{stay_increase}분({round(stay_increase/60, 1)}시간) 증가합니다. "
            f"정류장 반경 500m 이내 공실 임대료 보조 정책을 우선 배정하세요."
        )
        
    return CommercialSimResponse(
        town_name=req.target_town,
        selected_category_name=cat_name,
        original_cei=orig_cei,
        simulated_cei=sim_cei,
        cei_change_percent=cei_change_pct,
        expected_stay_increase_min=stay_increase,
        vacant_resolved_count=store_count,
        policy_recommendation=policy_msg,
        ml_formula=formula_str,
        data_basis={
            "original_cei": "기준지표: 전처리 단계에서 산출한 읍면동별 상권 엔트로피 또는 현재 기본값",
            "simulated_cei": "정책 시나리오: 선택 업종별 엔트로피 가중치 × 입점 점포 수 반영",
            "cei_change_percent": "시나리오 계산값: 기준 CEI 대비 변화율",
            "expected_stay_increase_min": "추정값: 회귀식 기반 정책효과 시나리오",
            "vacant_resolved_count": "정책 가정: 사용자가 입력한 입점 지원 점포 수",
        }
    )

# 🌟 12. 영남대 AI Gateway (Claude-sonnet-5) 기반 TII × CEI 융합 정책 자문서 생성 API
class PolicyReportRequest(BaseModel):
    town_name: str
    spot_name: Optional[str] = "바람의 언덕 / 신선대"
    original_interval: int = 120
    new_interval: int = 25
    original_tii: float = 0.95
    simulated_tii: float = 0.18
    category_name: str
    store_count: int
    original_cei: float
    simulated_cei: float
    cei_change_percent: float
    expected_stay_increase_min: int

class PolicyReportResponse(BaseModel):
    report_markdown: str
    model_used: str

@app.post("/api/generate-policy-report", response_model=PolicyReportResponse)
async def generate_policy_report(req: PolicyReportRequest):
    """
    학교 Mindlogic AI Gateway(Claude-sonnet-5)를 호출하여 TII(교통) x CEI(상권) 융합 행정 기획서 생성
    """
    import os
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(BASE_DIR.parent.parent / ".env", override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://factchat-cloud.mindlogic.ai/v1/gateway")

    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # 배차 단축 및 고립도 개선율
    interval_saved_min = req.original_interval - req.new_interval
    tii_improve_pct = round(((req.original_tii - req.simulated_tii) / req.original_tii) * 100, 1) if req.original_tii > 0 else 0

    prompt = f"""
당신은 한국관광 데이터랩 공모전에 출품하는 거제시 관광·교통 융합 정책 수석 행정자문관입니다.
거제시 외곽 관광지의 핵심 문제는 **"교통 고립(TII 高)과 상권 획일화(CEI 低)의 악순환"**입니다.
이 두 축을 동시에 해결하는 **[거제시 TII×CEI 융합형 관광 활성화 마스터플랜]**을 지자체 정식 공문서 양식으로 완결성 있게 작성해 주세요.

[실측 데이터 및 시뮬레이션 지표]
1. 대상 거점: 거제시 {req.town_name} [{req.spot_name}]
   - 데이터랩 팩트: 한국관광 데이터랩 실측 인기 명소 (Tmap 최상위권)
2. [축 1: 교통 인프라 TII 진단 및 시뮬레이션]
   - 현황: 주요 노선 배차 {req.original_interval}분 공백 (TII 교통고립도 {req.original_tii})
   - 셔틀 정책 투입: 도심(고현터미널) ↔ {req.town_name} 직통 관광 셔틀 투입
   - 효과: 배차간격 {req.original_interval}분 → {req.new_interval}분 ({interval_saved_min}분 대폭 단축), TII 고립도 {req.original_tii} → {req.simulated_tii} ({tii_improve_pct}% 개선)
3. [축 2: 상권 다양성 CEI 진단 및 시뮬레이션]
   - 현황: 기존 상권 다양성 지수(CEI) {req.original_cei} (획일화·편중 상권으로 관광객 조기 이탈)
   - 상권 정책 투입: 관광지 중심 반경 500m~1km 보행 상권 벨트 내 유휴·공실 상가에 '{req.category_name}' {req.store_count}개소 청년 창업 임대료 지원
   - 효과: 상권 엔트로피(CEI) {req.original_cei} → {req.simulated_cei} (+{req.cei_change_percent}% 다양화)
4. [축 3: 머신러닝(NumPy Ridge) 체류시간 통합 예측]
   - 회귀식: ΔStay = (2.13 × ΔInterval) + (411.8 × ΔCEI) + (121.9 × ΔVacancy) + 10.06
   - 예측 체류시간 증가: +{req.expected_stay_increase_min}분 (약 +{round(req.expected_stay_increase_min/60, 1)}시간 증가)
   - 거제시 평균 체류시간(기존 2,392.8분)과의 강력한 시너지 창출

[작성 요구사항]
- **문서 제목**: 「거제시 {req.town_name}({req.spot_name}) TII×CEI 융합형 관광 활성화 긴급 정책 제언서」
- **구체적 목차 구성**:
  - **Ⅰ. 추진 배경 및 실측 현황 분석** (데이터랩 검색 상위권이나 교통 고립 TII {req.original_tii} 및 상권 획일화 CEI {req.original_cei}의 복합 한계)
  - **Ⅱ. 교통-상권 동시 연계 핀셋 정책 실행안** (1. 도심 직통 주말 관광 셔틀 개설 / 2. 관광지 반경 500m~1km 보행 상권 벨트 청년 로컬 크리에이터 육성 조례 및 임대료 보조)
  - **Ⅲ. 머신러닝 예측 성과 및 경제적 파급효과** (체류시간 +{round(req.expected_stay_increase_min/60, 1)}시간 증가, 관광객 소비액 증대, 자가용 분산 탄소 저감)
  - **Ⅳ. 향후 행정 로드맵 및 예산 확보 방안** (지방소멸대응기금 및 국토부 스마트시티 챌린지 공모 연계)
- 중간에 말이 끊기지 않도록 결론(제언)까지 완전히 마무리하여 출력해 주세요.
- 가독성 높은 마크다운 표(Table)와 불릿포인트를 적극 활용해 주세요.
"""

    try:
        completion = client.chat.completions.create(
            model="claude-sonnet-5",
            messages=[
                {"role": "system", "content": "지자체 관광·도시교통 빅데이터 융합 정책 수석 연구원입니다. 공문서 및 전문 행정 기획서 형식으로 작성합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        report_text = completion.choices[0].message.content
        return PolicyReportResponse(
            report_markdown=report_text,
            model_used="claude-sonnet-5 (영남대 Mindlogic AI Gateway)"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Gateway 호출 오류: {str(e)}")

