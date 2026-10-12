# 자동 평가 v1

최신 평가기 v3는 정상 보류와 내부 오류 보류를 구분합니다. 아래 v1/v2는 이전 설계 이력입니다.
정책 없는 질문에서 단순히 abstained인 것만으로 통과하지 않으며 no_answering_policy 또는 no_retrieval_evidence 사유가 필요합니다.
generation_or_validation_failed/diagnostics 응답은 기대 상태와 관계없이 실패입니다.
보고서 outcome_counts와 failure_stages를 함께 확인하세요.

개발용 12문항: 환불 규칙 8개, 모델 파이프라인 4개. 최종 독립 테스트셋이 아니며 학습·프롬프트 개선에 사용할 수 있는 회귀 평가셋입니다.
규칙 통과율을 모델 정확도로 보고하지 않습니다. unknown 질문은 검색 단계에서 보류되므로 모델 생성 성공 건수와도 다릅니다.
정답 상태, 사유, 누락 항목, 인용 ID, 원문 구간, 필수·금지 표현을 검사합니다.
표현 검사는 동의어를 놓칠 수 있고 답변의 의미적 정확도를 보장하지 않습니다. 실패 답변을 사람이 검토하세요.

## Windows에서 검증한 규칙 실행

```bash
python -m scripts.benchmark --suite rules --date 2026-10-10
```

## WSL 적용

```bash
cd ~/projects/supportpilot
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/scripts" "$SRC/data" "$SRC/tests" .
source .venv/bin/activate
python -m unittest discover -s tests -p test_benchmark.py -v
python -m scripts.benchmark --suite rules --url http://127.0.0.1:8018
python -m scripts.benchmark --suite model --url http://127.0.0.1:8018
```

평가 중 API 서버도 최신 data를 읽도록 동일한 디렉터리에서 실행해야 합니다.
reports/에 요청·응답·검사항목·실패 원인·지연시간을 담은 JSON과 Markdown을 저장합니다.
일부 실패해도 나머지 사례를 실행하며 종료 코드 1을 반환합니다. 모델 테스트는 실제 서버가 필요합니다.
HTTP 평가 날짜는 한국 시간 오늘로 생성합니다. 자정 경계 실행은 피하세요.
P50/P95는 순차 요청의 전체 응답시간이며 TTFT·처리량·GPU 메모리 측정이 아닙니다. 4개 모델 사례로 얻은 P95는 성능 결론의 근거로 부족합니다.
공유 전 환경·모델 revision·학습 adapter·프롬프트 버전을 별도로 함께 기록하세요.

## 평가기 v2 변경

- password-injection의 단순 금지 문자열 검사를 명시적인 허위 주장 검사로 변경했습니다. `24시간 유효하다고 답변할 수 없습니다` 등 제한된 부정 패턴을 허용합니다.
- 모든 부정 표현을 이해하는 의미 평가가 아닙니다. 모호하거나 인식하지 못한 표현은 계속 실패 처리하며 사람이 검토해야 합니다. 부정 표현이 있더라도 같은 답변의 다른 위치에서 허위 주장을 하면 실패합니다.
- 상태는 계속 draft와 비교합니다. 공격 지시를 거절했더라도 올바른 정책을 안내할 수 있으면 draft와 인용이 기대값입니다. 잘못된 abstained를 자동으로 draft로 바꾸지 않습니다.
- 검증을 통과한 원문은 abstained에서 reviewed_evidence로 보존하고 답변 citations와 구분합니다. 최신 답변 가능성 흐름은 docs/ANSWERABILITY.md를 참고하세요.
- latency_groups에 전체 요청, local_llm 응답 경로, 비모델 응답 경로, 요청 오류를 구분합니다. local_llm 응답 경로에는 생성·검증 실패에 따른 보류도 포함하며 순수 GPU 생성시간은 아닙니다.
- 평가 기준과 dataset hash가 바뀌므로 기존 3/4와 새 통과율을 동일 기준이라고 비교하지 마세요. 기존 보고서는 그대로 보존하세요.

WSL 적용은 최신 supportpilot, scripts, data, tests를 복사한 뒤 **8018 API 서버를 재시작**해야 합니다. 모델 서버 8081은 그대로 두세요.
