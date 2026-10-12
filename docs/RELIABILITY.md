# 출력·의도 분기 수정 v2.1

1. 검색 1위가 환불 문서라도 환불/결제 취소/금액 반환 의도가 없으면 환불 규칙을 실행하지 않습니다. 구조화된 refund_facts 입력은 환불 의도를 명시한 것으로 취급합니다.
2. 전체 출력이 정확히 JSON 코드 블록으로 감싸진 경우만 블록을 제거합니다. 설명 속 JSON 추출/잘린 JSON 복구/배열 변환은 하지 않습니다.
3. JSON 오류에 문자 길이, 오류 위치, 종료 사유를 기록합니다. 모델 서버가 length이면 토큰 한도에 도달했을 가능성이 있습니다. 과거 실패가 코드 블록 때문이었는지는 확정할 수 없습니다.
4. 생성 입력에 판정 결과와 기대 상태를 전달합니다. 상태를 강제로 고치지 않고, 충돌 시 기대/실제 상태를 diagnostics에 기록합니다.
5. 상품명이 같아도 질문한 속성의 정책이 없으면 답변 근거가 없다는 지침을 보강했습니다.

서빙 lock은 유지되므로 동시 요청 처리량 개선은 이번 수정 범위가 아닙니다.
첫 최종 테스트 19/24 보고서는 보존하세요. 결과를 보고 개선했으므로 재평가는 동일 질문에 대한 회귀 평가입니다. final 파일과 hash는 변경하지 않았습니다.

## WSL 적용

8018 API를 중지하고 파일을 복사합니다.

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/tests" .
python -m unittest discover -s tests -p test_output_reliability.py -v
```

8081 모델 서버도 Ctrl+C로 종료하고 아래 명령으로 재시작하면 finish_reason 진단이 활성화됩니다. 모델을 다시 적재합니다.

```bash
python -m uvicorn scripts.model_server:app --host 127.0.0.1 --port 8081
```

API 터미널:

```bash
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

평가 터미널:

```bash
python -m scripts.benchmark --suite model --dataset development --url http://127.0.0.1:8018
python -m scripts.benchmark --suite model --dataset final --url http://127.0.0.1:8018
```

새 보고서 prompt_version=answerability-2.1을 확인하세요. 실제 모델의 상태 충돌 개선과 JSON 오류 원인은 재실행에서 확인해야 합니다.
