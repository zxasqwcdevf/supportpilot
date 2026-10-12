# 환경 확인: 2026-10-09

- RTX 5080, 16303MiB VRAM
- NVIDIA driver 595.97, nvidia-smi 표시 CUDA 최대 호환 버전 13.2
- 확인 시 사용 메모리 2319MiB. 가용량은 다른 프로세스에 따라 달라짐.
- nvidia-smi의 CUDA 표시는 설치된 toolkit/PyTorch 버전을 증명하지 않음.
- 기본 python 경로는 Python313, 실행 시 실제 위치 경고 발생.
- Codex bundled Python 3.12 실행 가능. 프로젝트 .venv에 FastAPI·uvicorn·pytest·httpx 설치 완료.
- wsl --list --verbose: Wsl/E_ACCESSDENIED. 설치 여부를 확정할 수 없음.

## 다음 GPU 환경 확인

일반 PowerShell에서 `wsl --list --verbose` 확인.
WSL Ubuntu 환경이 있다면 `nvidia-smi`와 Python 버전 확인 후 별도 가상환경 생성.
PyTorch는 공식 설치 선택기를 사용해 Blackwell 지원 wheel 선택.
`torch.cuda.is_available()`, device name, 실제 CUDA tensor 연산을 확인.
그 다음 4B 모델의 짧은 생성 테스트 후 서빙·양자화·QLoRA 호환성 확인.
OS/드라이버 설치 또는 재부팅은 아직 수행하지 않았음.
