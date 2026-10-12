# 판정 태스크 QLoRA 실험

기본 모델은 Qwen/Qwen3-4B-Instruct-2507입니다. 답변 생성 전체를 바꾸는 것이 아니라 answerability와 direct_evidence의 JSON 판정을 학습합니다. 현재 검수된 데이터는 train 48 / validation 16 / test 16이며 템플릿 기반의 작은 실험입니다. 학습 성공이나 validation loss 하락만으로 서비스 정확도 향상을 주장하지 않습니다.

`scripts/train_qlora.py`는 NF4 + double quantization, BF16 연산, LoRA rank 8 / alpha 16 / dropout 0.05, 배치 1 / gradient accumulation 8, learning rate 1e-4, 3 epochs, SDPA, gradient checkpointing을 사용합니다. assistant JSON과 종료 토큰에만 loss를 적용합니다. 길이 초과는 잘라내지 않고 오류를 출력합니다. test 파일은 열지 않습니다. train/validation의 개수·그룹·중복 질문과 manifest 그룹 중복을 검사합니다.

WSL 실행 순서:

```bash
cd ~/projects/supportpilot
python3 -m venv .venv-train
source .venv-train/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements-training.txt
python -m pip check
mkdir -p reports/environments
python -m pip freeze > reports/environments/training-packages.txt
python -m unittest tests.test_finetuning -v
python -m scripts.train_qlora --dry-run
```

기존 API 및 vLLM 환경과 분리합니다. 학습 전에 vLLM/Transformers 모델 서버를 해당 터미널에서 Ctrl+C로 종료하고 `nvidia-smi`로 GPU 메모리가 반환되었는지 확인합니다. 데이터 토큰화는 CPU에서 하므로 dry-run 때에는 서버를 종료하지 않아도 됩니다. bitsandbytes는 CUDA 12.8의 sm120 빌드를 지원하지만 실제 CUDA 커널 및 메모리 적합성은 WSL 시험 학습으로 확인해야 합니다.

```bash
python -m scripts.train_qlora --smoke --output runs/qlora-smoke-v1
cat runs/qlora-smoke-v1/metrics.json

# 시험 학습 성공 후 실행
python -m scripts.train_qlora --output runs/qlora-judgment-v1
cat runs/qlora-judgment-v1/metrics.json
```

출력 폴더가 이미 있으면 덮어쓰지 않습니다. 재시도는 새 --output 이름을 사용합니다. dry-run 길이 오류가 나면 실제 최대 길이에 맞춰 --max-length를 늘리고 GPU 메모리를 시험합니다. OOM이면 우선 서버가 종료되었는지 확인합니다. 이 데이터에서 학습량은 약 18 optimizer steps이므로 유의미한 일반화 성능 검증에는 추가 질문군이 필요합니다.

`adapter/`는 LoRA 가중치와 tokenizer를 저장합니다. 원본 모델 가중치는 변경하지 않습니다. epoch별 validation loss로 가장 낮은 checkpoint를 선택합니다. `metrics.json`은 loss, 실행 시간, PyTorch peak allocated/reserved 메모리를 기록하며 프로세스 전체 GPU 점유와는 다릅니다. `run_config.json`은 모델 revision, 데이터 SHA, 라이브러리 버전과 설정을 기록합니다. revision이 기록되면 재현 실험에 --revision으로 그 commit을 지정하세요.

아직 adapter는 API에 적용되지 않습니다. 다음 단계에서 기본 모델과 adapter를 동일한 validation 입력·프롬프트로 비교해야 합니다. 학습 데이터의 간략한 system prompt는 실제 서비스 prompt와 다르므로 runtime 회귀 평가도 별도로 필요합니다. test 세트는 설정을 확정한 후 한 번 평가합니다.

공식 근거: [PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization), [bitsandbytes 설치](https://huggingface.co/docs/bitsandbytes/v0.50.2/en/installation), [Transformers Trainer](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer).
