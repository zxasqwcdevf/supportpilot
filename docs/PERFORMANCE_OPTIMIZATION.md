# 성능 최적화 1차: 시작 워밍업 / vLLM 비교

판정 prompt_version=answerability-2.3은 변경하지 않았습니다. GPU 서버를 교체하면 생성 결과가 달라질 수 있으므로 품질 회귀가 필요합니다.
실제 WSL/vLLM 실행은 이 세션에서 수행하지 않았습니다. 개선 수치는 아래 실험 후 확인합니다.

## A. Transformers 기준값 + API 워밍업

API 8018만 중지하고 기존 .venv에서 파일을 복사합니다. Transformers 모델 서버 8081은 유지합니다.

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/tests" .
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
export SUPPORTPILOT_WARMUP=1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

Application startup complete가 나올 때까지 기다립니다. 검색 인덱스 로딩과 정상 질문 1건을 시작 단계에서 수행합니다.
초기화 비용이 사라지는 것이 아니라 시작 단계로 이동합니다. /health.warmup에 검색/모델 시간을 기록합니다.
warmup.ready는 초기 요청 성공을 뜻하며 앞으로의 모든 요청 성공을 보장하지 않습니다.
model_loaded 필드는 원격 GPU 상태를 확인하지 않으므로 false를 유지하며 model_path_warmed를 확인하세요.
SUPPORTPILOT_WARMUP=0이면 워밍업을 끌 수 있습니다.

평가용 터미널:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
curl http://127.0.0.1:8018/health
python -m scripts.performance --label transformers --requests 24 --concurrency 1 2 4
```

reports/performance-transformers-*.json 저장. API 시작 워밍업 결과와 벤치마크 워밍업은 별도입니다.

## B. 별도 vLLM 환경 구축

기존 PyTorch 학습/Transformers 환경에 설치하지 않고 새 환경으로 분리합니다.

```bash
cd ~/projects/supportpilot
python3 -m venv .venv-vllm
source .venv-vllm/bin/activate
python -m pip install --upgrade pip
pip install vllm
pip freeze > requirements-vllm.lock.txt
python -c 'import torch,vllm; print("vllm:",vllm.__version__,"torch:",torch.__version__,"cuda:",torch.version.cuda); print(torch.cuda.get_device_name(0))'
```

공식 설치 문서: https://docs.vllm.ai/en/stable/getting_started/installation/gpu/
vLLM wheel의 CUDA/PyTorch 조합과 GPU 지원을 확인하세요. 버전 설치가 실패하면 로그를 확인한 뒤 대응하며 기존 .venv는 보존합니다.

## C. GPU 서버 교체

**8018 API와 Transformers 8081 서버를 둘 다 중지**하세요. 두 생성 서버를 단일 16GB GPU에 동시에 적재하지 않습니다.
.venv-vllm 터미널에서:

```bash
cd ~/projects/supportpilot
source .venv-vllm/bin/activate
nvidia-smi
bash scripts/start_vllm.sh
```

시작값: BF16, context 4096, max-num-seqs 4, GPU memory utilization 0.80, prefix caching enabled.
이는 5080에 대한 실측 확정값이 아닙니다. 메모리 부족 시 다른 GPU 프로세스를 확인하고 max-num-seqs=2 또는 context 축소를 별도 실험으로 기록하세요.
가용 메모리가 예약 목표보다 적으면 시작을 거부할 수 있습니다. 낮은 utilization이 항상 해결되는 것은 아니며 모델/KV 캐시 공간을 확보해야 합니다.
컴파일/초기화에는 시간이 걸릴 수 있습니다. /health가 준비될 때까지 API를 시작하지 않습니다.

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8081/v1/models
```

별도 API 터미널은 **기존 .venv** 사용:

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
export SUPPORTPILOT_WARMUP=1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

## D. 동일 품질·성능 재평가

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
python -m scripts.benchmark --suite model --dataset development --url http://127.0.0.1:8018
python -m scripts.benchmark --suite model --dataset final --url http://127.0.0.1:8018
python -m scripts.performance --label vllm --requests 24 --concurrency 1 2 4
```

비교 자료: Transformers/vLLM 성능 JSON 2개 + vLLM 품질 JSON.
확인: 품질 회귀, 내부 오류, 동시성별 P50/P95, 초당 완료 요청, 시작 워밍업 시간.
동일 질문 혼합/요청수/판정 버전으로 비교합니다. label은 사용자가 지정한 값이며 GPU backend를 자동 검증하지 않습니다.
prefix caching 때문에 반복 질문에서 측정한 처리량은 새로운 질문의 처리량과 다를 수 있습니다.
GPU memory/TTFT는 이 도구가 측정하지 않으며 GPU 메모리는 nvidia-smi 기록으로 별도 첨부하세요.
성능 기준을 맞추려고 품질 테스트 기대값을 변경하지 않습니다.

## 원복

vLLM과 API를 종료하고 기존 .venv에서 scripts.model_server:app을 8081로 실행한 뒤 API를 다시 시작합니다.
API 설정과 모델 ID가 동일해 코드 수정 없이 원복 가능합니다.

## vLLM 0.31 시작 오류: nvcc 없음

사용자 로그의 직접 원인은 FlashInfer sampler JIT에서 CUDA 컴파일러 nvcc를 찾지 못한 것입니다.
설치 조합은 vLLM 0.31.0 / PyTorch 2.13.0+cu130 / CUDA runtime 13.0입니다.
start_vllm.sh는 VLLM_USE_FLASHINFER_SAMPLER를 기본 0으로 설정해 native sampler 경로를 먼저 사용합니다.
공식 저장소의 동일 오류 보고와 우회: https://github.com/vllm-project/vllm/issues/49497
이 변경은 sampler에만 적용되며 다른 CUDA JIT 경로에 toolkit이 필요할 가능성까지 제거하지 않습니다.
실제 WSL 시작 성공은 아직 확인하지 않았습니다. 우선 재실행 로그로 확인하고, 다른 root cause가 나오면 별도로 처리하세요.
성능 비교 기록에는 sampler= native, VLLM_USE_FLASHINFER_SAMPLER=0을 함께 남기세요.
