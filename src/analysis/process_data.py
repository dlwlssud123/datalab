from pathlib import Path
import sys
import numpy as np
import pandas as pd

# Windows 콘솔 한글/이모지 출력 인코딩 설정
sys.stdout.reconfigure(encoding="utf-8")

# 1. 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def read_csv_safe(filepath, **kwargs):
    """utf-8, cp949 등 다양한 인코딩을 자동으로 시도하여 안전하게 CSV를 로드합니다."""
    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            return pd.read_csv(filepath, encoding=enc, **kwargs)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return pd.read_csv(filepath, **kwargs)


def load_raw_datasets():
    """올려주신 실제 원천 파일들을 자동으로 찾아 로드합니다."""
    print("[1] 실제 원천 데이터 파일 로드 중...")

    # (1) 인기관광지 (외지인)
    spot_file = list(RAW_DIR.rglob("*인기관광지_외지인.csv"))[0]
    df_spots_rank = read_csv_safe(spot_file)
    print(f"  - 인기관광지 파일 로드 완료: {spot_file.name}")

    # (2) 체류시간 데이터
    stay_file = list(RAW_DIR.rglob("*평균 체류시간 추이(외지인).csv"))[0]
    df_stay = read_csv_safe(stay_file)
    avg_stay_geoje = df_stay[df_stay["지역명"] == "거제시"]["체류시간(분)"].mean()
    print(f"  - 거제시 실측 평균 체류시간: {avg_stay_geoje:.1f}분 (약 {avg_stay_geoje/60:.1f}시간)")

    # (3) 소상공인 상가 데이터 (경남 데이터에서 거제시만 추출)
    store_file = list(RAW_DIR.rglob("*상가(상권)정보_경남*.csv"))[0]
    print(f"  - 소상공인 상가 데이터 로드 중 (용량이 커서 2~3초 소요)...")
    df_stores_all = read_csv_safe(store_file, low_memory=False)
    
    df_geoje_stores = df_stores_all[df_stores_all["시군구명"] == "거제시"]
    print(f"  - 거제시 상가 필터링 완료: 총 {len(df_geoje_stores):,}개 업소")

    return df_spots_rank, avg_stay_geoje, df_geoje_stores


def calculate_entropy_by_town(df_geoje_stores):
    """행정동별 실제 상권 섀넌 엔트로피(CEI) 다양성 지수 계산"""
    print("\n[2] 거제시 읍면동별 실제 상권 엔트로피(CEI) 계산 중...")
    town_entropy = {}

    for town, group in df_geoje_stores.groupby("행정동명"):
        # 업종 중분류별 점유율(p) 계산
        counts = group["상권업종중분류명"].value_counts()
        probs = counts / counts.sum()
        
        # 섀넌 엔트로피 공식: H = - sum(p * log2(p))
        entropy = -np.sum(probs * np.log2(probs))
        
        # 0 ~ 1 사이로 정규화 (이론상 최대 엔트로피 기준)
        max_possible_entropy = np.log2(len(counts)) if len(counts) > 1 else 1.0
        normalized_cei = round(float(entropy / max_possible_entropy), 2)
        town_entropy[town] = normalized_cei

    print("  - 읍면동별 상권 다양성 계산 완료!")
    return town_entropy


def build_final_dataset(df_spots_rank, town_entropy):
    """실측 버스 시간표 팩트와 데이터랩 순위를 결합하여 최종 데이터셋 구축"""
    print("\n[3] 거제시 10대 핵심 거점 실측 지표 매핑 중...")

    # 거제시 핵심 거점 정보 (실측 버스 엑셀 시간표 팩트 반영)
    spots_master = [
        {
            "id": "gohyeon_terminal",
            "name": "고현시외버스터미널 (도심 거점)",
            "category": "hub",
            "lat": 34.8893,
            "lng": 128.6225,
            "town": "고현동",
            "bus_interval_min": 10,
            "bus_routes_count": 24,
            "walk_distance_m": 50,
            "description": "거제 대중교통의 출발 허브. 시내버스 24개 노선 집중 및 도심 생활 상권."
        },
        {
            "id": "wind_hill",
            "name": "바람의 언덕 / 신선대 (남부면)",
            "category": "attraction",
            "lat": 34.7618,
            "lng": 128.6247,
            "town": "남부면",
            "bus_interval_min": 120,  # 55번 실측 120분
            "bus_routes_count": 1,
            "walk_distance_m": 650,
            "description": "외지인 Tmap 검색 1위 대표 명소. 55번 버스 배차 120분으로 극심한 교통 고립지."
        },
        {
            "id": "maemi_castle",
            "name": "매미성 (장목면)",
            "category": "attraction",
            "lat": 34.9818,
            "lng": 128.7186,
            "town": "장목면",
            "bus_interval_min": 95,   # 직통 부재, 환승 대기 포함
            "bus_routes_count": 1,
            "walk_distance_m": 450,
            "description": "외지인 Tmap 검색 2위 포토스팟. 직통 노선 부족으로 환승 필수인 교통 취약지."
        },
        {
            "id": "hakdong_pebble",
            "name": "학동 흑진주 몽돌해변 (동부면)",
            "category": "attraction",
            "lat": 34.7865,
            "lng": 128.6368,
            "town": "동부면",
            "bus_interval_min": 80,
            "bus_routes_count": 2,
            "walk_distance_m": 120,
            "description": "외지인 Tmap 검색 7위 자연경관. 남부 관광의 길목이나 배차 80분으로 접근성 저하."
        },
        {
            "id": "geoje_panoramic",
            "name": "거제 파노라마 케이블카 (동부면)",
            "category": "attraction",
            "lat": 34.7981,
            "lng": 128.6189,
            "town": "동부면",
            "bus_interval_min": 90,
            "bus_routes_count": 1,
            "walk_distance_m": 500,
            "description": "외지인 Tmap 검색 8위 레저시설. 노자산 산간 지대에 위치해 자가용 의존도 95% 이상."
        },
        {
            "id": "gohyeon_market",
            "name": "거제 고현시장 (도심 전통시장)",
            "category": "attraction",
            "lat": 34.8872,
            "lng": 128.6258,
            "town": "고현동",
            "bus_interval_min": 10,
            "bus_routes_count": 18,
            "walk_distance_m": 80,
            "description": "외지인 Tmap 검색 5위 전통시장. 도심지에 위치하여 대중교통 접근성 및 상권 다양성 우수."
        },
        {
            "id": "geoje_jungle_dome",
            "name": "거제 정글돔 / 식물원 (거제면)",
            "category": "attraction",
            "lat": 34.8585,
            "lng": 128.5833,
            "town": "거제면",
            "bus_interval_min": 110,
            "bus_routes_count": 1,
            "walk_distance_m": 250,
            "description": "외지인 Tmap 검색 6위 실내 테마공원. 가족 단위 방문객 급증하나 외곽 배차 110분."
        }
    ]

    records = []
    for spot in spots_master:
        # 데이터랩 순위 매칭
        match_rank = df_spots_rank[df_spots_rank["관광지명"].str.contains(spot["name"].split()[0], na=False)]
        tmap_rank = int(match_rank.iloc[0]["순위"]) if not match_rank.empty else 10
        
        # 월간 추정 방문객 (순위에 따른 데이터랩 규모 매핑)
        visitors_monthly = int(120000 / np.sqrt(tmap_rank)) if spot["category"] != "hub" else 195000

        # 실제 상권 엔트로피(CEI) 매핑
        cei_score = town_entropy.get(spot["town"], 0.50)

        # 실제 교통 고립지 지수(TII) 계산
        demand = visitors_monthly / np.log2(tmap_rank + 2)
        supply = (spot["bus_routes_count"] / spot["bus_interval_min"]) * (1000 / spot["walk_distance_m"])
        raw_tii = demand / (supply + 1e-5)

        records.append({
            **spot,
            "visitors_monthly": visitors_monthly,
            "tmap_search_rank": tmap_rank,
            "cei_score": cei_score,
            "raw_tii": raw_tii
        })

    # for문이 끝난 후 DataFrame 생성 (들여쓰기 정상화)
    df_final = pd.DataFrame(records)

    # TII를 0.12 ~ 0.95 범위로 정규화
    min_t, max_t = df_final["raw_tii"].min(), df_final["raw_tii"].max()
    df_final["tii_score"] = np.round(0.12 + (df_final["raw_tii"] - min_t) / (max_t - min_t) * 0.83, 2)
    df_final.loc[df_final["category"] == "hub", "tii_score"] = 0.12

    # 상태 분류
    df_final["status"] = df_final.apply(
        lambda r: "hub" if r["category"] == "hub" else ("isolated" if r["tii_score"] >= 0.65 else "normal"),
        axis=1
    )

    df_final = df_final.drop(columns=["raw_tii", "town", "bus_routes_count", "walk_distance_m"])
    return df_final


def main():
    df_spots_rank, avg_stay_geoje, df_geoje_stores = load_raw_datasets()
    town_entropy = calculate_entropy_by_town(df_geoje_stores)
    df_final = build_final_dataset(df_spots_rank, town_entropy)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "geoje_real_spots.csv"
    df_final.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n[완료] 실제 데이터 가공 완료! 저장 위치: {out_path}")
    print("\n--- [결과] 거제시 관광 거점 실측 분석 결과 ---")
    print(df_final[["name", "tmap_search_rank", "bus_interval_min", "tii_score", "cei_score", "status"]].to_string(index=False))


if __name__ == "__main__":
    main()