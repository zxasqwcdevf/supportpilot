# CPU 자동 테스트

`.github/workflows/ci.yml`은 main push, 모든 pull request, 수동 workflow_dispatch에서 실행됩니다. Ubuntu runner와 Python3.12에서 editable 설치 및 pytest 전체 테스트를 실행합니다. pytest 종료 코드가 실패하면 job도 실패합니다.

`.[dev]`만 설치하며 torch, vLLM, 학습·임베딩 패키지는 설치하지 않습니다. 모델 서버 URL은 비우고 검색은 keyword, 시작 워밍업은 끕니다. 모델·임베딩 경로 테스트는 mock을 사용하며 실제 GPU 품질 평가를 대신하지 않습니다. HF offline 설정은 모델 다운로드를 막는 설정이며 pip 의존성 설치 자체는 네트워크가 필요합니다.

추적된 가상 정책·평가 데이터는 checkout에서 함께 읽습니다. DB는 runner.temp에 생성합니다. JUnit XML은 실행 후 cpu-test-results artifact로 7일간 보존합니다. 설치 단계에서 실패해 XML이 없으면 upload 단계를 건너뛰는 효과만 있고 원래 설치 실패는 유지됩니다.

로컬의 API 환경에서도 같은 명령을 실행할 수 있습니다:

```bash
source .venv/bin/activate
SUPPORTPILOT_MODEL_URL='' SUPPORTPILOT_RETRIEVAL=keyword SUPPORTPILOT_WARMUP=0 \
  python -m pytest -q --junitxml=/tmp/supportpilot-junit.xml
```

GitHub에 workflow를 push한 뒤 Actions → CPU tests → 최신 실행에서 초록색 성공을 확인합니다. 실패하면 해당 step 로그를 확인합니다. 로컬 성공은 GitHub runner 성공과 다릅니다. 최초 hosted 실행 결과는 아직 확인하지 않았습니다.

공식 참고: https://docs.github.com/en/actions/tutorials/build-and-test-code/python
