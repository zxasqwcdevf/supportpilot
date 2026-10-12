# 최종 테스트와 성능 측정

최종 질문 24개를 작성하고 SHA256 manifest로 고정했습니다. 정확히 같은 질문은 기존 개발/검증 질문과 겹치지 않습니다.
동일한 가상 정책·유사 주제를 바탕으로 만든 작은 전향 평가셋입니다. 외부 도메인 일반화를 증명하지 않습니다.
아직 실제 모델로 실행하지 않았습니다. 처음 실행한 보고서를 보존하고 이 질문으로 튜닝하면 해당 세트는 회귀셋이 됩니다.
문구 검사의 오탐은 사람이 검토하되 원래 자동 점수와 수동 판정 결과를 별도로 기록하세요.
파일이 바뀌면 평가를 거부합니다. 통과하도록 질문/manifest를 재생성하지 마세요.

## 1. WSL 파일 적용

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/data" "$SRC/tests" .
python -m unittest discover -s tests -p test_datasets.py -v
```

현재 API 판정 버전은 유지하므로 8018 서버가 최신 answerability-2.0이면 최종 테스트 실행 전에 재시작할 필요 없습니다.

## 2. 최종 품질 측정

```bash
python -m scripts.benchmark --suite model --dataset final --url http://127.0.0.1:8018
```

reports/model-final-*.json 생성. 정상 답변/정책 부재/오류 보류를 구분해 읽습니다.
실패해도 보고서는 저장되며 종료 코드 1을 반환합니다.

## 3. 초기화와 동시 요청 측정

첫 요청 비용을 보려면 8018 API만 재시작하세요. 모델 서버가 이미 실행 중이면 모델 로딩 자체의 cold start는 포함되지 않습니다.
API 터미널:

```bash
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

다른 터미널:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
python -m scripts.performance --url http://127.0.0.1:8018 --requests 12 --concurrency 1 2 4
```

initial_probe: API 프로세스 첫 요청. warmups: 질의 3개. runs: 동시성별 12개 요청.
수 분 걸릴 수 있습니다. 표준 Transformers 서버의 lock은 GPU 생성을 직렬화하므로 동시성이 높다고 처리량이 비례하지 않습니다.
successful latency는 정상 처리된 응답만, all_p95_ms는 오류도 포함합니다. 완료율은 정확도가 아닙니다.
입력 혼합은 두 정상 질문과 한 정책 부재 질문이므로 각각 호출 횟수가 다릅니다. 이 혼합을 고정한 상태로만 버전을 비교하세요.
첫 초기화와 GPU 서버 로딩은 별개이며 TTFT/VRAM/token throughput은 이 도구에서 측정하지 않습니다.
reports/performance-*.json을 저장하며 정상 응답 내용 품질은 최종 품질 평가에서 별도로 확인합니다.
