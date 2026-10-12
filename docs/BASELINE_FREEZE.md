# 기준 버전 보존

releases/supportpilot-v2.3-code.zip과 manifest에 source SHA256을 저장했습니다.
실험 baseline 보고서/기획·설계/테스트/화면 소스 포함. .venv, 사용자 SQLite 상담 이력, 모델 가중치는 제외했습니다.
이 snapshot은 학습 데이터 준비 코드 추가 전의 기준 코드입니다. 현재 진행 중인 데이터 도구는 별도 변경입니다.
스크립트 capture_baseline은 이미 존재하는 zip을 덮어쓰지 않습니다.

WSL에서 현재 실행 환경도 기록하세요:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
python -m scripts.capture_runtime --label api
deactivate
source .venv-vllm/bin/activate
python -m scripts.capture_runtime --label vllm
```

reports/environments에 package name/version, OS/Python, GPU driver/memory, 허용 목록의 설정, 캐시된 모델 revision을 저장합니다.
캐시 revision이 실제 실행 server revision과 같은지 확인해야 합니다. 과거 측정 환경을 소급 확정하지 않습니다.
서버 재시작/변경 전에 시작 스크립트 설정과 버전 파일을 함께 보관합니다.
