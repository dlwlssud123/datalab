from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

APP_MAIN = ROOT_DIR / "src" / "app" / "main.py"
PROCESS_DATA = ROOT_DIR / "src" / "analysis" / "process_data.py"
TRAIN_REGRESSION = ROOT_DIR / "src" / "analysis" / "train_regression.py"
INDEX_HTML = ROOT_DIR / "src" / "app" / "templates" / "index.html"
REGRESSION_WEIGHTS = ROOT_DIR / "src" / "analysis" / "regression_weights.json"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SPOTS_CSV = PROCESSED_DIR / "geoje_real_spots.csv"
BUS_CSV = PROCESSED_DIR / "bus_schedule_summary.csv"
VACANCY_CSV = PROCESSED_DIR / "vacancy_rate_summary.csv"

SELECTED_SPOT_TO_TOWN = {
    "maemi_castle": "장목면",
    "wind_hill": "남부면",
    "hakdong_pebble": "동부면",
    "geoje_jungle_dome": "거제면",
}

REQUIRED_SPOT_COLUMNS = {
    "id",
    "name",
    "category",
    "lat",
    "lng",
    "visitors_monthly",
    "tmap_search_rank",
    "bus_interval_min",
    "tii_score",
    "cei_score",
    "status",
    "description",
    "vacancy_rate_pct",
    "vacancy_market_name",
    "vacancy_rate_source_url",
}

REQUIRED_BUS_COLUMNS = {
    "spot_id",
    "bus_interval_min",
    "bus_routes_count",
    "bus_schedule_source",
}

REQUIRED_VACANCY_COLUMNS = {
    "spot_id",
    "vacancy_market_name",
    "vacancy_rate_quarter",
    "vacancy_rate_pct",
    "vacancy_linkage_level",
    "vacancy_rate_source_url",
}


class ValidationError(Exception):
    pass


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str) -> None:
    raise ValidationError(message)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def assert_status(response: Any, expected: int, label: str) -> dict[str, Any] | list[Any]:
    if response.status_code != expected:
        fail(f"{label}: expected HTTP {expected}, got {response.status_code} / {response.text}")
    return response.json()


def check_python_compile() -> None:
    for path in [APP_MAIN, PROCESS_DATA, TRAIN_REGRESSION]:
        assert_true(path.exists(), f"missing Python file: {path}")
        py_compile.compile(str(path), doraise=True)
    ok("Python 문법 검사 통과")


def check_processed_files() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in [SPOTS_CSV, BUS_CSV, VACANCY_CSV, REGRESSION_WEIGHTS, INDEX_HTML]:
        assert_true(path.exists(), f"missing required artifact: {path}")

    spots = pd.read_csv(SPOTS_CSV)
    bus = pd.read_csv(BUS_CSV)
    vacancy = pd.read_csv(VACANCY_CSV)

    assert_true(len(spots) >= 7, f"geoje_real_spots.csv should contain at least 7 rows, got {len(spots)}")
    assert_true(REQUIRED_SPOT_COLUMNS.issubset(spots.columns), f"spots CSV missing columns: {sorted(REQUIRED_SPOT_COLUMNS - set(spots.columns))}")
    assert_true(REQUIRED_BUS_COLUMNS.issubset(bus.columns), f"bus CSV missing columns: {sorted(REQUIRED_BUS_COLUMNS - set(bus.columns))}")
    assert_true(REQUIRED_VACANCY_COLUMNS.issubset(vacancy.columns), f"vacancy CSV missing columns: {sorted(REQUIRED_VACANCY_COLUMNS - set(vacancy.columns))}")
    assert_true(spots["id"].is_unique, "spot id must be unique")
    assert_true(spots["bus_interval_min"].min() > 0, "bus_interval_min must be positive")
    assert_true(spots["tii_score"].between(0, 1).all(), "tii_score must be between 0 and 1")
    assert_true(spots["cei_score"].between(0, 1).all(), "cei_score must be between 0 and 1")
    assert_true(spots["vacancy_rate_pct"].notna().all(), "all spots must have vacancy_rate_pct")

    weights = json.loads(REGRESSION_WEIGHTS.read_text(encoding="utf-8"))
    for key in ["coef_interval", "coef_cei", "coef_vacancy", "intercept", "formula"]:
        assert_true(key in weights, f"regression_weights.json missing key: {key}")

    ok("processed CSV/회귀 가중치 산출물 검사 통과")
    return spots, bus, vacancy


def check_api_contract(spots_csv: pd.DataFrame) -> None:
    from src.app.main import app

    client = TestClient(app)
    health = assert_status(client.get("/api/health"), 200, "GET /api/health")
    assert_true(health.get("spots_loaded", 0) >= 7, "health.spots_loaded must be at least 7")

    spots = assert_status(client.get("/api/spots"), 200, "GET /api/spots")
    assert_true(isinstance(spots, list), "/api/spots must return list")
    assert_true(len(spots) == len(spots_csv), "/api/spots row count must match processed CSV")
    spot_by_id = {spot["id"]: spot for spot in spots}

    for spot_id in SELECTED_SPOT_TO_TOWN:
        assert_true(spot_id in spot_by_id, f"/api/spots missing selected spot: {spot_id}")
        response = assert_status(
            client.post("/api/simulate", json={"target_spot_id": spot_id, "shuttle_count": 2}),
            200,
            f"POST /api/simulate {spot_id}",
        )
        assert_true(
            response["original_interval_min"] == int(spot_by_id[spot_id]["bus_interval_min"]),
            f"simulate original interval mismatch for {spot_id}",
        )

    assert_status(
        client.post("/api/simulate", json={"target_spot_id": "missing_spot", "shuttle_count": 2}),
        404,
        "POST /api/simulate unknown spot",
    )
    assert_status(
        client.post("/api/simulate", json={"target_spot_id": "wind_hill", "shuttle_count": 9}),
        422,
        "POST /api/simulate invalid shuttle_count",
    )

    for spot_id, town in SELECTED_SPOT_TO_TOWN.items():
        response = assert_status(
            client.post(
                "/api/simulate-commercial",
                json={"target_town": town, "store_category": "local_fnb", "new_store_count": 1},
            ),
            200,
            f"POST /api/simulate-commercial {town}",
        )
        assert_true(
            abs(float(response["original_cei"]) - float(spot_by_id[spot_id]["cei_score"])) < 1e-9,
            f"commercial CEI mismatch for {spot_id}/{town}",
        )
        assert_true("original_vacancy_rate_pct" in response, f"commercial response missing vacancy field for {town}")

    assert_status(
        client.post(
            "/api/simulate-commercial",
            json={"target_town": "없는면", "store_category": "local_fnb", "new_store_count": 1},
        ),
        400,
        "POST /api/simulate-commercial unknown town",
    )
    assert_status(
        client.post(
            "/api/simulate-commercial",
            json={"target_town": "남부면", "store_category": "bad", "new_store_count": 1},
        ),
        400,
        "POST /api/simulate-commercial unknown category",
    )
    assert_status(
        client.post(
            "/api/simulate-commercial",
            json={"target_town": "남부면", "store_category": "local_fnb", "new_store_count": 0},
        ),
        422,
        "POST /api/simulate-commercial invalid store count",
    )
    assert_status(
        client.post(
            "/api/generate-policy-report",
            json={
                "town_name": "남부면",
                "category_name": "로컬",
                "store_count": 0,
                "original_cei": 1.2,
                "simulated_cei": 0.7,
                "cei_change_percent": 10,
                "expected_stay_increase_min": -1,
            },
        ),
        422,
        "POST /api/generate-policy-report invalid payload",
    )

    ok("API 정상/예외 응답 계약 검사 통과")


def extract_profile_values(index_text: str, spot_id: str) -> dict[str, float]:
    pattern = rf"'{re.escape(spot_id)}':\s*\{{(?P<body>.*?)\n\s*\}}"
    match = re.search(pattern, index_text, re.DOTALL)
    if not match:
        fail(f"frontend profile missing: {spot_id}")

    body = match.group("body")
    values: dict[str, float] = {}
    for key in ["origInterval", "origTii", "origCei"]:
        value_match = re.search(rf"{key}:\s*([0-9.]+)", body)
        if not value_match:
            fail(f"frontend profile {spot_id} missing {key}")
        values[key] = float(value_match.group(1))
    return values


def check_frontend_backend_consistency(spots_csv: pd.DataFrame) -> None:
    index_text = INDEX_HTML.read_text(encoding="utf-8")
    spot_by_id = spots_csv.set_index("id").to_dict(orient="index")

    for spot_id in SELECTED_SPOT_TO_TOWN:
        profile = extract_profile_values(index_text, spot_id)
        spot = spot_by_id[spot_id]
        assert_true(profile["origInterval"] == float(spot["bus_interval_min"]), f"frontend origInterval mismatch for {spot_id}")
        assert_true(abs(profile["origTii"] - float(spot["tii_score"])) < 1e-9, f"frontend origTii mismatch for {spot_id}")
        assert_true(abs(profile["origCei"] - float(spot["cei_score"])) < 1e-9, f"frontend origCei mismatch for {spot_id}")

    for required_snippet in [
        "currentSpotData?.bus_interval_min",
        "commData.vacancy_change_pctp",
        "original_vacancy_rate_pct",
        "vacancy_rate_basis",
    ]:
        assert_true(required_snippet in index_text, f"frontend missing API-linked snippet: {required_snippet}")

    ok("프론트-백엔드 기준값 정합성 검사 통과")


def main() -> int:
    try:
        check_python_compile()
        spots, _bus, _vacancy = check_processed_files()
        check_api_contract(spots)
        check_frontend_backend_consistency(spots)
    except ValidationError as e:
        print(f"[FAIL] {e}")
        return 1
    except Exception as e:
        print(f"[ERROR] {e.__class__.__name__}: {e}")
        return 1

    print("\n전체 실행 검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
