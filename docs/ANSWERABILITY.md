# 답변 가능성 판정 v1

최신 버전은 아래 v2 구조이며, 기존 v1 설명은 개발 이력입니다.

검색 점수는 질문에 답할 근거가 있다는 보장이 아닙니다. 검색 후 생성 전에 같은 4B 모델로 정책의 답변 가능성을 판정합니다.

- answerable: 질문의 기능·상품에 직접 답할 정책이 있음
- missing_user_facts: 직접 답할 정책은 있지만 적용에 필요한 사용자 사실이 부족함. 누락 항목을 명시해야 함
- no_policy: 직접 답할 정책이 없음. 답변 생성을 건너뛰고 abstained로 반환

no_policy 응답은 citations=[]입니다. reviewed_documents는 검색해 검토한 문서의 ID·제목·버전이며 답변 근거가 아닙니다.
생성 모델이 abstained를 반환하면서 유효한 원문을 함께 보냈을 때는 reviewed_evidence로 보존하고 citations에는 넣지 않습니다.
판정/생성 상태 불일치나 잘못된 ID/JSON은 기존 generation_or_validation_failed로 보류합니다.
판정에서 선택한 supporting_ids의 문서만 답변 생성에 전달합니다.

## 성능과 한계

no_policy는 모델 호출 1회, 답변 생성은 2회입니다. 응답시간이 늘어날 수 있습니다.
판정도 모델 기반이므로 정답을 보장하지 않습니다. 문자열 유사도가 높지만 질문에 답하지 못하는 정책을 잘못 고를 수 있습니다.
유효한 인용 원문만으로 답변 내용이 논리적으로 지지되는지는 보장하지 않습니다.
이번에 확인한 이메일/API/SAML/기업 상품 실패 사례를 개발 피드백으로 사용했으므로 기존 validation을 최종 독립 테스트로 보고하지 않습니다.
검색 임계값과 질문 기대값은 바꾸지 않았습니다. 검색 보류율과 최종 답변 보류율은 계속 구분합니다.

## WSL 적용

8018 API 서버만 Ctrl+C로 중지한 후:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/tests" .
python -m unittest discover -s tests -p test_answerability.py -v
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

다른 터미널에서:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
python -m scripts.benchmark --suite model --dataset development --url http://127.0.0.1:8018
python -m scripts.benchmark --suite model --dataset validation --url http://127.0.0.1:8018
```

실제 모델 판정은 아직 이 세션에서 실행하지 않았습니다. 실패 사례와 정상 질문 회귀를 모두 재평가하세요.

## 진단과 판정 프롬프트 v1.1

실패 응답 diagnostics에 failed_stage/error_type/error_code를 추가했습니다.
answerability: 판정 스키마/지원 문서 ID 검사, generation: 생성 호출,
*.transport: HTTP/외부 JSON 실패, *.json_decode: 모델 본문의 JSON 해석 실패,
status_consistency: 판정과 생성 상태 불일치, citation_validation: 출력·인용 검사입니다.
단계 정보가 없던 과거 보고서의 오류 원인은 소급 확정할 수 없습니다.
성공 응답 stage_ms는 판정과 생성 호출 시간을 구분하며 prompt_version=answerability-1.1을 반환합니다.
평가 보고서 failure_stages는 실패 사례별 단계를 집계합니다. evaluation_checks는 응답을 받았으나 평가 조건이 실패했음을 뜻합니다.
raw 모델 출력/사용자 질문을 diagnostics에 추가 저장하지 않습니다. 기존 평가 보고서에는 요청·응답이 기록됩니다.
판정 프롬프트에도 공격 지시를 거부하더라도 실제 정책으로 답할 수 있으면 answerable이라는 기준을 추가했습니다.
재시도나 상태 강제 변경은 추가하지 않았습니다. 실제 회귀 개선 여부는 WSL 재평가로 확인합니다.

## 판정 구조 v2 / 평가기 v3

prompt_version=answerability-2.0, evaluator_version=3.0.
모델이 출력하는 첫 분기는 has_answering_policy의 엄격한 JSON boolean입니다.

정책 없음:

```json
{"has_answering_policy": false}
```

정책 있음:

```json
{"has_answering_policy": true, "needs_user_facts": false, "supporting_ids": ["password-v1"], "missing_fields": []}
```

false이면 source/user facts 필드는 적용 대상이 아니므로 제거하고 내부 decision=no_policy로 변환합니다.
true이면 반드시 유효한 문서 ID를 제공해야 하며, needs_user_facts=true이면 부족한 항목을 명시해야 합니다.
true+빈 supporting_ids 오류를 false로 바꾸지 않습니다. 문자열 "false" 역시 오류입니다.
판정과 생성 상태 일치 검사 및 오류 보류는 유지합니다. 모델 호출 횟수는 늘리지 않았습니다.

평가기의 no_internal_error 검사는 diagnostics 또는 generation_or_validation_failed를 실패로 처리합니다.
기대 상태가 abstained이면 no_answering_policy/no_retrieval_evidence 사유도 확인합니다.
outcome_counts는 answered_or_clarified, policy_absence_abstention, retrieval_abstention, internal_error_abstention, unclassified_abstention, request_error를 구분합니다.
답변 생성 단계의 분류되지 않은 보류는 기대값 abstained인 사례에서도 통과하지 않습니다.
최근 기존 검증 보고서의 10/10은 올바른 판정 6개와 오류 보류 4개였으며, 새 기준으로는 6/10입니다. 기존 보고서는 수정하지 않고 보존합니다.
모델의 실제 false 판정 정확도는 WSL 재실행으로 확인해야 합니다.
