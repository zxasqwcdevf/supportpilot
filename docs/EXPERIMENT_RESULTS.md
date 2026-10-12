# v2.3 품질 및 서빙 비교

원본: reports/baselines/*.json. 사용자 WSL 실행 결과이며 provenance에 첨부 ID 기록.
모델 Qwen3-4B-Instruct-2507 BF16, GPU RTX 5080 16GB, 판정 answerability-2.3.
hybrid 검색, 기본 threshold BM25=2.0/dense=0.8, API 시작 워밍업 활성화.
vLLM 0.31.0, PyTorch 2.13.0+cu130, FlashInfer sampler 비활성화, native sampler.
vLLM context=4096, max-num-seqs=4, GPU memory utilization=0.8, prefix caching 활성화.
Transformers 최초 환경 확인은 torch 2.11.0+cu128이었으며 정확한 성능 실행 시 freeze와 모델 commit revision은 아직 보고서에 없습니다.
라이브러리/런타임도 달라지므로 서빙 엔진만의 순수 인과 효과로 해석하지 않습니다.

## 품질

첫 고정 질문 평가: 19/24. 피드백 반영 후 같은 회귀 질문에서 v2.3 Transformers 24/24, vLLM 24/24.
반복 개선한 소규모 동일 도메인 회귀셋의 결과이며 외부 질문에 대한 100% 정확도 주장이 아닙니다.

## 부하 측정: 3개 질문 혼합, 각 동시성 24건

| 동시성 | Transformers P95 초 | vLLM P95 초 | Transformers 건/초 | vLLM 건/초 |
|---|---:|---:|---:|---:|
| 1 | 4.349 | 1.634 | 0.365 | 0.917 |
| 2 | 7.545 | 1.749 | 0.388 | 1.676 |
| 4 | 14.485 | 1.963 | 0.381 | 2.993 |

동시성4에서 초당 정상 완료 약7.86배, P95 약86.4% 감소. 두 backend 모두 각 총72건 내부 오류0.
반복 질문/prefix caching의 영향이 있으며 새로운 질문 처리량으로 일반화하지 않습니다.
판정+직접근거검증+생성 3회 경로와 정책부재1회 경로가 혼합되어 있습니다.
전체 응답시간은 큐 대기 포함, TTFT/token throughput/VRAM은 측정하지 않았습니다.

## 재현 기록 보완

WSL에서 `pip freeze > requirements-api.lock.txt`, vLLM 환경에서 `pip freeze > requirements-vllm.lock.txt`를 보관합니다.
모델 snapshot commit, GPU driver, startup 옵션, OS, CPU/RAM, cutoff, cache 상태를 함께 기록하세요.
보고서에 없는 정보는 추정값으로 확정하지 않습니다. 기존 보고서는 덮어쓰지 않습니다.
