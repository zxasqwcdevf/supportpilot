# WSL에서 모델 연결

기존 WSL 가상환경을 사용합니다. 아래 복사 명령은 프로젝트 소스만 복사하며 Windows .venv는 복사하지 않습니다.

```bash
source ~/projects/supportpilot/.venv/bin/activate
cd ~/projects/supportpilot
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/data" "$SRC/tests" .
pip install fastapi uvicorn pytest httpx
python -m uvicorn scripts.model_server:app --host 127.0.0.1 --port 8081
```

첫 실행은 모델을 다운로드하고 BF16으로 GPU에 적재합니다. 외부 네트워크에 서버를 공개하지 않습니다.
두 번째 WSL 터미널:

```bash
source ~/projects/supportpilot/.venv/bin/activate
cd ~/projects/supportpilot
curl http://127.0.0.1:8081/health
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

세 번째 터미널:

```bash
curl http://127.0.0.1:8018/api/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"연간 결제했는데 환불 가능한가요?"}'
```

브라우저에서 http://localhost:8018/docs 접속.
모델 서버 연결에 실패하거나 JSON/인용 검증이 실패하면 reason=generation_or_validation_failed와 함께 답변을 보류합니다.
모델 URL을 설정하지 않으면 기존 추출형 기준선으로 동작합니다.
API /health의 model_server_configured는 설정 여부이며 실제 GPU 적재 성공을 뜻하지 않습니다. 모델 서버 /health의 loaded를 확인하세요.

## 검증 한계

### 환불 조건 누락 수정 (2026-10-10)

환불 관련 검색 결과에 구조화된 decision 정책이 있으면 생성 모델 대신 정책 원문+확인 질문을 반환합니다.
status=needs_information, mode=policy_rule, validation=policy_template로 출처를 명확히 표시합니다.
상품·결제일·사용 이력은 refund_facts 구조화 입력으로 받습니다. 질문의 자유 텍스트에서 사실을 추출하지 않습니다.
누락 항목만 required_fields에 반환합니다. 모든 조건 충족 시 draft, 그 외 requires_review로 반환합니다.
입력 사실은 사용자 제공 정보이며 실제 결제 기록 검증이나 환불 실행은 수행하지 않습니다.
이 규칙은 환불 정책에 한정되며 일반적인 의미 검증 기능이 아닙니다. 다른 문의는 기존 모델 생성 경로를 사용합니다.

수정 적용: 두 번째 터미널의 API 서버만 Ctrl+C로 중지하고 다음을 실행하세요. GPU 모델 서버는 재시작할 필요 없습니다.

```bash
cd ~/projects/supportpilot
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/data" "$SRC/tests" .
source .venv/bin/activate
python -m unittest discover -s tests -p 'test_refund.py' -v
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

### 구조화 입력 예시

```json
{
  "question": "연간 요금제 환불해주세요",
  "refund_facts": {
    "plan": "annual",
    "payment_date": "2026-10-09",
    "usage_history": false
  }
}
```

plan은 annual/monthly, payment_date는 YYYY-MM-DD, usage_history는 JSON boolean입니다.
누락 또는 null은 미확인으로 처리합니다. 문자열 "false"는 422 오류입니다.
서버의 한국 시간 날짜와 결제일의 달력 날짜 차이가 0~7일이면 기간 조건 충족으로 해석합니다.
정확한 결제 시각을 사용하는 168시간 기준이 필요하면 정책과 입력 스키마를 별도로 변경해야 합니다.
미래 결제일은 정정을 요청합니다. monthly 요금제는 이 연간 정책만으로 환불 가능/불가를 판단하지 않습니다.
입력된 사실은 대화 간 저장되지 않으므로 후속 요청에도 이전에 입력한 항목을 함께 보내세요.

수정 적용 후 테스트:

```bash
python -m unittest discover -s tests -p 'test_refund*.py' -v
python -m pytest tests -q
```

인용 ID 허용 목록·원문 구간·JSON 구조를 검사합니다. 답변 내용이 인용으로 논리적으로 뒷받침되는지는 자동 보장하지 않습니다.
현재 검색은 키워드 기준선입니다. 임베딩·BM25·reranker는 후속 작업입니다.
GPU 모델 서버는 이 세션에서 실행하지 않았습니다. 한국어 품질·GPU 호환성·메모리 사용량은 WSL에서 실측해야 합니다.
