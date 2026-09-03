import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 1. .env 로드
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# 2. 클라이언트 초기화
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://factchat-cloud.mindlogic.ai/v1/gateway"),
)

# 3. LLM 호출 테스트
response = client.chat.completions.create(
    model="claude-sonnet-5",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)

