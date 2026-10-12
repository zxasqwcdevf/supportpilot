# 현재 진행 상태

1. 실제 WSL 상담 UI: 테스트 문의 생성/수정 승인/새로고침 후 승인 이력 다시 열기 확인. 서버 프로세스 재시작은 직접 수행하지 않음.
2. 운영 기준 코드: v2.3 source ZIP과 파일/아카이브 hash 보존. 실제 WSL 환경 정보는 capture_runtime 명령으로 추가 기록해야 함.
3. 학습 준비: 사용자가 WSL에서 10개 그룹을 검수하고 train48/validation16/test16 분할 성공을 보고함. WSL의 검수 기록과 prepared 파일은 로컬 deliverable로 가져오지 않음.
4. 실제 QLoRA 학습: 사용자 보고로 3 epochs/18 steps 완료. train loss 0.1204228, validation loss 0.1963315, 로딩 포함 83.416초, peak allocated 5.83 GiB / reserved 7.133 GiB, test 미사용. 이 수치는 사용자가 제공한 결과이며 로컬 GPU 재실행 결과가 아님.
5. 기본 모델/어댑터 validation 비교: 동일 NF4 base에서 adapter 활성/비활성 비교 코드 구현. 평가기6개 및 토큰화/분할4개 테스트 통과. 실제 GPU 비교와 서비스 적용은 아직 실행하지 않음. 실행 가이드는 QLORA_COMPARISON.md.

160개 후보의 schema/ID 중복/기존 평가셋 정확한 질문 중복과 ZIP hash/무결성을 확인했습니다.
현재 변경에 대한 전체 API 테스트 재실행은 Windows sandbox socket 제한으로 완료되지 않았습니다. 기존 상담 기능은 이전 전체80개 테스트와 이번 실제 UI 검증으로 확인했습니다.
기존 vLLM 모델과 품질 기준은 변경하지 않았습니다.
