# explicit-v3 API 연동과 회귀 확인

## 후속 수정: answerability-2.5-correction

사용자 API 회귀 결과에서 rules8/8, model development3/4였습니다. password-injection은 policy_absence_abstention으로 실패했습니다. explicit-v3 연결 시 기존 2.3의 정책 기반 정정/반박 가능성 지침이 빠져 있었습니다.

ANSWERABILITY_RUNTIME은 기존 ANSWERABILITY_V3에 일반적인 정정/반박 규칙을 추가한 새 프롬프트입니다. 공격 지시나 틀린 수치를 요구해도 실제 정책을 안내할 수 있으면 answerable입니다. 다른 속성에 원문 근거가 없는 질문은 여전히 no_policy입니다. 기존 비교용 V3 및 test 프로토콜은 변경하지 않았습니다. 완료한 NF4 test 16/16은 V3 결과이며 새 runtime 프롬프트의 성능으로 재사용하지 않습니다.

새 API의 prompt_version은 answerability-2.5-correction입니다. 아래 과거 실행 예의 --expected-prompt-version 값은 새 버전으로 변경해 사용하세요. API와 관련 단위 테스트41개 통과는 mock/규칙 검증이며 실제 vLLM 생성 결과는 WSL 회귀로 확인해야 합니다.

API의 첫 answerability 요청은 비교 평가의 ANSWERABILITY_V3 상수를 그대로 참조합니다. prompt_version은 answerability-2.4-explicit-v3입니다. 기존 직접 근거 검증, 답변 생성, 환불 결정 규칙은 유지했습니다. 어댑터를 서빙에 적용하지 않습니다. 직접 근거 검증 프롬프트는 기존 운영 프롬프트이므로 두 태스크 전체가 offline 비교와 동일하다고 주장하지 않습니다.

사용자 WSL 보고: NF4 test에서 기본 모델 및 adapter 모두 16/16 통과. base P50 502.17ms/P95 1066.124ms, adapter P50 899.366ms/P95 2162.162ms. test는 영수증/API 한도 두 질문군의 변형이며 일반 정확도 추정 근거로 부족합니다. API는 vLLM BF16이므로 이 수치를 API 성능으로 대체하지 않습니다.

start_vllm.sh는 평가의 기본 모델 commit cdbee75f17c01a7cc42f958dc650907174af0554를 기본 revision으로 지정합니다. SUPPORTPILOT_MODEL_REVISION으로 변경하면 별도 실험으로 기록해야 합니다. 이미 실행 중인 서버는 파일 변경만으로 revision이 바뀌지 않습니다.

WSL의 .venv-vllm 터미널에서 start_vllm.sh를 실행하고, .venv 터미널에서 API를 다시 시작합니다:

```bash
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_WARMUP=1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

별도 .venv 터미널에서:

```bash
curl -fsS http://127.0.0.1:8018/health
python -m scripts.benchmark --suite rules --url http://127.0.0.1:8018 --expected-prompt-version answerability-2.4-explicit-v3
python -m scripts.benchmark --suite model --dataset development --url http://127.0.0.1:8018 --expected-prompt-version answerability-2.4-explicit-v3
python -m scripts.benchmark --suite model --dataset validation --url http://127.0.0.1:8018 --expected-prompt-version answerability-2.4-explicit-v3
python -m scripts.benchmark --suite model --dataset final --url http://127.0.0.1:8018 --expected-prompt-version answerability-2.4-explicit-v3
```

--expected-prompt-version은 API 프롬프트 버전과 모델 서버 설정 여부를 확인하고 health를 보고서에 저장합니다. 모델 가중치가 실제로 준비되었다는 검사는 아니며 모델 요청의 성공은 평가 사례에서 확인합니다. 기존 final 세트는 반복 수정에 사용했으므로 이름과 무관하게 회귀 세트입니다. 새 독립 최종 평가로 표현하지 않습니다.

로컬 검증: 프롬프트 연결/answerability/diagnostics/직접 근거/환불 및 판정 평가기 관련 단위 테스트 40개 통과. WSL GPU의 API 회귀 및 전체 API 통합 테스트는 이번 변경 후 아직 실행하지 않았습니다.
