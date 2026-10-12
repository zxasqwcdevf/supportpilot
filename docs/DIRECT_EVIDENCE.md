# 직접 근거 검증 v2.2

최신 버전은 v2.3입니다. 아래 v2.2는 이전 설계 기록입니다.
v2.3에서는 코드가 정책 원문을 문장 구간으로 나누고 snippet_id와 시작/끝 위치를 부여합니다.
검증 모델은 directly_supported boolean과 snippet_ids만 출력하며 원문을 직접 작성하지 않습니다.
검증 결과 evidence는 코드가 선택한 ID의 실제 원문으로 구성합니다. 알 수 없는 ID 또는 빈 선택은 오류입니다.
질문의 틀린 전제를 정책으로 반박할 수 있어도 답변 가능으로 판정하도록 지침을 보강했습니다.
검증 호출이 하나 더 추가되지는 않아 모델 호출 횟수는 v2.2와 같습니다.
snippet 분할은 단순 문장부호 기준이므로 복잡한 문서/소수/약어에는 추가 개선이 필요합니다.
구간 선택의 의미적 적합성은 여전히 모델 판단입니다. 실제 회귀 개선은 WSL에서 확인해야 합니다.

검색 → 답변 가능성 판정 → 직접 근거 검증 → 생성 순서입니다.
판정이 정책 있음으로 나온 경우, 선택된 문서와 원래 질문만 추가 모델 호출에 전달합니다.
이 호출에는 이전 판정을 전달하지 않습니다. 같은 모델을 사용하므로 통계적으로 독립적인 검증이라고 주장하지 않습니다.
검증은 상품명 일치가 아니라 질문한 속성의 값/방법/조건/명시적 미지원 여부를 설명하는 원문을 요구합니다.
directly_supported=false이면 생성을 건너뛰고 no_answering_policy로 보류합니다.
true이면 문서 ID와 정확한 원문 구간을 코드로 검증합니다. 없는 원문/잘못된 JSON은 오류 보류로 처리되며 평가 성공이 아닙니다.
원문 존재를 코드로 검증해도 의미적 관련성은 모델 판단이므로 실제 API 한도 회귀 개선을 보장하지 않습니다.

## 비용

초기 판정 no_policy는 1회, 직접 근거 없음은 2회, 정상 생성은 3회 모델 호출입니다.
stage_ms.direct_evidence를 추가했으며 prompt_version=answerability-2.2입니다.
동시 요청 처리량 개선은 이번 변경에 포함하지 않았습니다. 정확도와 지연시간을 함께 비교하세요.
첫 고정셋 평가 19/24, 수정 후 회귀 23/24는 모두 보존하고 새 결과를 별도 기록합니다.

## 적용

8018 API 서버만 중지하고 파일 복사 후 재시작합니다. 8081 모델 서버는 그대로 사용합니다.

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/tests" .
python -m unittest discover -s tests -p test_direct_evidence.py -v
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

다른 터미널에서:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
python -m scripts.benchmark --suite model --dataset development --url http://127.0.0.1:8018
python -m scripts.benchmark --suite model --dataset final --url http://127.0.0.1:8018
```

final-unsupported-quota가 abstained/no_answering_policy인지 확인하고 정상 질문에 과도한 보류가 생기지 않았는지도 확인하세요.
