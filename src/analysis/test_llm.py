import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 1. .env 파일 경로 명시적 지정 로드
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# 2. 환경변수 추출 (export 접두사나 따옴표/공백 자동 정제)
raw_key = os.getenv("OPENAI_API_KEY")

# 혹시 .env에 'export OPENAI_API_KEY=...' 로 적혀있을 경우 대비
if not raw_key:
    raw_key = os.getenv("export OPENAI_API_KEY")

api_key = raw_key.strip().strip('"').strip("'") if raw_key else None
base_url = os.getenv("OPENAI_BASE_URL", "https://factchat-cloud.mindlogic.ai/v1/gateway").strip().strip('"').strip("'")

print("=" * 60)
print("🔍 [영남대 Mindlogic Gateway] 연결 진단")
print(f"🔗 Base URL: {base_url}")

if not api_key:
    print("❌ [오류] OPENAI_API_KEY를 .env에서 찾을 수 없습니다!")
    print("   👉 .env 파일에 아래처럼 적혀있는지 확인해 주세요:")
    print("      OPENAI_API_KEY=실제발급받은키")
    exit(1)

if api_key == "YOUR_API_KEY" or "YOUR_API_KEY" in api_key:
    print("❌ [오류] API 키 값에 플레이스홀더 'YOUR_API_KEY'가 그대로 적혀 있습니다!")
    print("   👉 FactChat 플랫폼 대시보드에서 발급받으신 실제 API 키로 교체해 주세요.")
    exit(1)

masked_key = api_key[:4] + "*" * max(0, len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else "***"
print(f"🔑 API Key 로드 완료 (길이: {len(api_key)}자, 형태: {masked_key})")
print("=" * 60)

# 3. 공식 문서 권장 OpenAI 클라이언트 초기화
client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

def run_test():
    # 1) 지원 모델 목록 조회
    print("\n📋 1. 지원 모델 목록 조회 중...")
    available_models = []
    try:
        models_response = client.models.list()
        for m in models_response.data:
            available_models.append(m.id)
        print(f"✅ 조회 성공! 지원 모델 수: {len(available_models)}개")
        print(f"   (예: {', '.join(available_models[:5])})")
    except Exception as e:
        print(f"⚠️ 모델 목록 조회 중 오류 (계속 진행): {e}")

    # 사용할 모델 선택 (공식 문서 기본값인 claude-sonnet-5 또는 gpt-4o-mini)
    target_model = "claude-sonnet-5" if "claude-sonnet-5" in available_models else (
        "gpt-4o-mini" if "gpt-4o-mini" in available_models else (available_models[0] if available_models else "claude-sonnet-5")
    )
    print(f"\n🚀 2. '{target_model}' 모델로 거제시 정책 질의 생성 테스트...")

    try:
        response = client.chat.completions.create(
            model=target_model,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 거제시 관광 및 교통 활성화 정책을 자문하는 수석 전문 컨설턴트입니다."
                },
                {
                    "role": "user",
                    "content": "거제시 남부면(바람의 언덕)은 외지인 검색 1위이나 버스 배차가 120분입니다. 지자체가 즉시 추진해야 할 맞춤형 정책 2가지를 3줄로 간결히 제시해 주세요."
                }
            ],
            temperature=0.7,
            max_tokens=300
        )
        print("\n--- 📝 [LLM 정책 제언 응답] ---")
        print(response.choices[0].message.content)
        print("-------------------------------")
        print("🎉 [성공] 영남대 AI Gateway LLM 연결 및 생성 완료!")

    except Exception as e:
        print(f"❌ 생성 호출 실패: {e}")

if __name__ == "__main__":
    run_test()