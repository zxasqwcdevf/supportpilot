#!/usr/bin/env bash
set -euo pipefail
# Avoid FlashInfer sampler JIT requiring nvcc on a runtime-only WSL install.
# Explicitly set to 1 when testing the toolkit-backed FlashInfer path.
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
# Run in a separate .venv-vllm after stopping the Transformers GPU server.
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-4B-Instruct-2507 \
  --revision "${SUPPORTPILOT_MODEL_REVISION:-cdbee75f17c01a7cc42f958dc650907174af0554}" \
  --served-model-name Qwen/Qwen3-4B-Instruct-2507 \
  --host 127.0.0.1 --port 8081 \
  --dtype bfloat16 \
  --max-model-len 4096 \
  --max-num-seqs 4 \
  --gpu-memory-utilization 0.80 \
  --enable-prefix-caching
