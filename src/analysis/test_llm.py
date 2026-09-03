import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

# 1. .env 로드
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")
if not api_key:
    raw = os.getenv("export OPENAI_API_KEY", "")
    api_key = raw.strip().strip('"').strip("'")

base_url = "https://factchat-cloud.mindlogic.ai/v1/gateway"

print("=" * 60)
print("🔍 [Mindlogic Gateway 정밀 연결 진단]")
print(f"🔗 Base URL: {base_url}")
if api_key:
    masked = api_key[:5] + "*" * max(0, len(api_key) - 9) + api_key[-4:]
    print(f"🔑 API Key: {masked} (총 {len(api_key)}글자)")
else:
    print("❌ API Key가 비어 있습니다!")
print("=" * 60)


def test_with_http_headers():
    """공식 curl 문서에 정의된 2가지 인증 방식(Bearer, x-api-key) 및 끝 슬래시를 직접 테스트"""
    payload = {
        "model": "claude-sonnet-5",
        "messages": [{"role": "user", "content": "거제시 관광 활성화 방안 1줄 요약"}],
        "max_tokens": 100
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    test_cases = [
        ("1. OpenAI 스타일 (Authorization: Bearer, 슬래시 포함)", f"{base_url}/chat/completions/", {"Authorization": f"Bearer {api_key}"}),
        ("2. OpenAI 스타일 (Authorization: Bearer, 슬래시 없음)", f"{base_url}/chat/completions", {"Authorization": f"Bearer {api_key}"}),
        ("3. Anthropic 스타일 (x-api-key, 슬래시 포함)", f"{base_url}/chat/completions/", {"x-api-key": api_key}),
        ("4. Anthropic 스타일 (x-api-key, 슬래시 없음)", f"{base_url}/chat/completions", {"x-api-key": api_key}),
    ]

    for title, url, headers in test_cases:
        print(f"\n▶ 테스트: {title}")
        print(f"  - URL: {url}")
        req_headers = {"Content-Type": "application/json", **headers}
        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                content = res_body["choices"][0]["message"]["content"]
                print(f"  🎉 [성공!] 응답:\n  {content.strip()}")
                return title, url, headers
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"  ❌ HTTP {e.code}: {err_body}")
        except Exception as e:
            print(f"  ❌ 기타 에러: {e}")

    return None, None, None


if __name__ == "__main__":
    success_title, success_url, success_headers = test_with_http_headers()
    if success_title:
        print("\n" + "=" * 60)
        print(f"✅ 최적의 성공 조합 발견: {success_title}")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("⚠️ 4가지 방식 모두 401이 발생했습니다.")
        print("   👉 이는 API 키 문자열 자체가 게이트웨이 서버에 미등록되었거나 만료되었음을 의미합니다.")
        print("=" * 60)