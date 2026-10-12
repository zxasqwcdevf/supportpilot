# 검색·답변 검증 단계

새 검증셋은 검색 20문항(관련 12, 무관 8), 답변 10문항입니다.
기존 개발 질문과 정확히 같은 문장은 없으며 설정을 변경하지 않은 상태에서 먼저 평가합니다.
동일 정책으로 작성한 수동 검증셋이므로 완전히 독립된 도메인/최종 테스트가 아닙니다.
이 결과로 cutoff나 prompt를 튜닝한 뒤에는 별도 최종 테스트셋을 준비해야 합니다.

특히 가입 이메일 변경/API 키/SAML/기업 요금제처럼 문서의 단어와 겹치지만 답변 근거가 없는 질문을 포함했습니다.
이때 검색 결과가 반환되면 검색 보류 검사는 실패합니다. 모델이 검색된 정책을 보고도 정보 부족으로 보류할 수 있으므로 전체 답변 평가도 별도로 확인합니다.
문구 검사로 생긴 실패는 사람이 답변을 읽고 검토하며 정답 수치/조건을 바꾸지 않은 표현 차이와 실제 오류를 구분합니다.

## Windows에서 새 질문에 대한 최초 결과

설정 변경 없이 BM25 cutoff=2.0으로 실행했습니다.
keyword Recall@3=0.542, MRR@3=0.583, 음성 보류율=0.75.
bm25 Recall@3=0.958, MRR@3=1.0, 음성 보류율=0.0.
12개 양성 질문 중 복수 정답 사례에서 한 문서를 놓칠 수 있어 MRR=1.0과 Recall<1.0은 모순이 아닙니다.
임베딩과 전체 답변은 아직 실행하지 않았습니다. 쉬운 개발 음성 2개에서의 개선이 어려운 음성 8개로 일반화되지 않는다는 결과를 보존합니다.

## WSL 소스 적용과 검색 검증

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/data" "$SRC/tests" .
python -m scripts.evaluate_retrieval --dataset validation --methods keyword bm25 hybrid
```

## 전체 답변 검증

8018 API 서버만 중지한 뒤 해당 터미널에서 실행합니다. 8081 모델 서버는 계속 사용합니다.

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_BM25_THRESHOLD=2.0
export SUPPORTPILOT_DENSE_THRESHOLD=0.8
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

별도 터미널에서:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
python -m scripts.benchmark --suite model --dataset development --url http://127.0.0.1:8018
python -m scripts.benchmark --suite model --dataset validation --url http://127.0.0.1:8018
```

reports/retrieval-validation-*.json과 model-validation-*.json을 함께 검토합니다.
검색 검증 프로세스의 워밍업은 API 프로세스와 공유되지 않아 첫 API 요청에 초기화 비용이 추가될 수 있습니다.
평가 실패 시 종료 코드 1이며 보고서에는 나머지 사례도 모두 기록됩니다.
