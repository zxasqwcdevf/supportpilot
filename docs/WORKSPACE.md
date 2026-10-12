# 상담 작업실 / 승인 이력

API 같은 서버의 /에서 상담 UI를 제공합니다. 추가 프런트엔드 설치가 필요 없습니다.
문의 → 생성 초안과 인용 → 상담원 수정 → 승인/반려 → 최근 문의 다시 열기.
검증: 전체 테스트 80개 통과, unittest subtest 8개 통과. HTTP case API와 정적 파일 제공까지 확인했습니다.
JavaScript 문법 검사를 통과했습니다. Windows 샌드박스의 테스트 서버에 인앱 브라우저가 연결되지 않아 시각 검증과 실제 브라우저 클릭 검증은 미완료입니다.
후속 확인: WSL 서버의 실제 UI에서 테스트 문의 생성 → 답변 수정 → 승인 → 페이지 새로고침 → 승인 이력 다시 열기까지 확인했습니다. 화면 증거는 reports/ui/approved-case.jpg입니다. 서버 프로세스 재시작 후 유지 여부는 이번 브라우저 확인에 포함하지 않았으며 SQLite 연결 간 영속성은 테스트했습니다.
환불 정보는 선택 입력입니다. 모르는 항목을 임의로 채우지 않습니다.
보류·상담원 확인 응답은 원문 그대로 승인할 수 없으며 검토자가 새 답변을 작성해야 합니다.
초안 원본과 최종 답변은 별도 저장하고 완료된 검토는 덮어쓰지 않습니다.
새 /api/cases 경로만 저장하며 기존 /api/questions 평가 요청은 DB에 저장하지 않습니다.

## 저장

기본 DB: runtime/supportpilot.sqlite3. SUPPORTPILOT_DB 환경변수로 바꿀 수 있습니다.
API 재시작 후에도 이력이 유지됩니다. runtime은 Git에서 제외했습니다.
최근 목록은 최대 50건, 서버는 데이터 전체를 보관합니다.
현재 검토자 이름은 직접 입력하며 계정 인증이 아닙니다. localhost 개인 데모용이며 다중 사용자 운영에는 인증/권한 설계가 필요합니다.
수정 답변은 모델의 인용 검증을 다시 수행하지 않으므로 사람이 원문을 확인해야 합니다.
승인/반려는 로컬 기록이며 고객 전송 또는 실제 환불을 실행하지 않습니다.

## WSL 적용

8018만 중지하고 복사하세요. vLLM 8081은 유지합니다.

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/tests" .
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
export SUPPORTPILOT_WARMUP=1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

http://localhost:8018/ 접속.
검토 순서: 초안 만들기 → 인용 확인 → 검토자 이름 입력 → 답변 수정/승인 → 최근 문의 다시 열기.

## 실험 결과

reports/baselines에 사용자가 제공한 원본 WSL 보고서 4개를 저장했습니다.
provenance는 파일 출처이며 이 세션에서 재실행한 결과가 아닙니다.
docs/EXPERIMENT_RESULTS.md에 품질·성능 비교와 측정 조건을 기록했습니다.
