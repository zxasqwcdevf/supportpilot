# 공개용 실험 결과 요약

기준일: 2026-10-12. 실제 GPU 실행 결과는 사용자 WSL 보고에 근거합니다. 문서 작성 환경에서 GPU 실험을 재실행한 것은 아닙니다.

## 모델 학습

Qwen/Qwen3-4B-Instruct-2507, RTX5080에서 NF4 + BF16 QLoRA를 실행했습니다. LoRA r=8, alpha=16, 배치1, 누적8, 학습률1e-4, 3 epochs/18 steps입니다. 그룹 검수 후 train48/validation16/test16으로 나눴으며 loss는 assistant 정답에 적용했습니다.

| 항목 | 결과 |
| --- | --- |
| train loss | 0.1204228 |
| validation loss | 0.1963315 |
| 모델 로딩 포함 시간 | 83.416초 |
| PyTorch peak allocated / reserved | 5.83 / 7.133 GiB |

loss는 답변 정확도가 아닙니다. 예약 메모리는 전체 프로세스 GPU 점유와 다릅니다.

## 고정 test 비교

평가기 judgment-comparison-1.2, prompt explicit-v3, 동일한 NF4 base와 저장 tokenizer를 사용했습니다. base는 adapter 비활성, adapter는 활성 상태입니다.

| 지표 | 기본 모델 | 어댑터 |
| --- | --- | --- |
| 전체 통과 | 16/16 | 16/16 |
| 스키마 준수 | 16/16 | 16/16 |
| 정답 근거 ID 일치 | 8/8 | 8/8 |
| P50 | 502.170ms | 899.366ms |
| P95 | 1,066.124ms | 2,162.162ms |

어댑터의 추가 품질 이득이 관찰되지 않았고 측정 지연이 길어 기본 모델을 선택했습니다. test는 영수증 발급/Pro API 한도 두 질문군의 변형으로 일반 정확도100%의 근거가 아닙니다. 단일 생성 측정이며 운영 부하 비교가 아닙니다. base 조건에도 비활성 adapter가 메모리에 남아 있습니다.

집계 보고서를 내보낸 뒤: [test 비교](../reports/public/qlora-test.json).

## 서빙 성능 비교 (v2.3)

3개 질문 혼합, 각 동시성24건, backend별72건, 내부 오류0건입니다.

| 동시성 | Transformers P95 | vLLM P95 | Transformers 처리량 | vLLM 처리량 |
| --- | --- | --- | --- | --- |
| 1 | 4.349초 | 1.634초 | 0.365건/초 | 0.917건/초 |
| 2 | 7.545초 | 1.749초 | 0.388건/초 | 1.676건/초 |
| 4 | 14.485초 | 1.963초 | 0.381건/초 | 2.993건/초 |

동시성4에서 처리량 약7.86배, P95 약86.4% 감소를 관찰했습니다. 반복 질문/prefix cache, 라이브러리·CUDA 런타임 차이의 영향이 있어 엔진만의 인과 효과나 새로운 질문 성능으로 일반화하지 않습니다. 최신 API 프롬프트의 부하 재측정값은 아닙니다.

근거: [Transformers 집계](../reports/public/transformers-performance-v2.3.json), [vLLM 집계](../reports/public/vllm-performance-v2.3.json).

## API 회귀와 자동 테스트

최신 API prompt_version은 answerability-2.6-restored이며 vLLM BF16 + hybrid 검색을 사용합니다. 사용자는 development/validation/기존 final 회귀의 전체 통과를 확인했습니다. 최신 상세 보고서를 문서 작성 환경으로 가져오지 않았으므로 현재 수치화된 지연은 제시하지 않습니다. final은 반복 개선에 사용한 회귀 세트이며 QLoRA의 보류 test와 별개입니다.

WSL 전체 pytest94개/subtest8개 통과 보고가 있었고, 이후 추가한 GitHub Actions CPU tests도 사용자 확인으로 통과했습니다. 최초 workflow의 runner.temp 위치 오류를 수정했습니다. CPU CI는 모델 추론이나 GPU 품질 검증을 대체하지 않습니다. [실제 Actions 기록](https://github.com/zxasqwcdevf/supportpilot/actions)을 참고하세요.

## 보고서 공개 방법

원본을 통째로 공개하지 않고 export_public_report 도구로 숫자 집계와 고정된 메타데이터만 내보냅니다. 질문/응답 본문, 상담 기록, DB, checkpoint 경로, URL, 환경 변수는 제외합니다. source_sha256으로 원본과의 연결을 기록합니다. 공개 JSON은 원본 전체나 재실행 결과가 아닌 집계 사본입니다. 이미 존재하는 출력은 덮어쓰지 않습니다.

```bash
python -m scripts.export_public_report --kind comparison \
  --source reports/qlora-test-1791634670809981343.json \
  --output reports/public/qlora-test.json

python -m scripts.export_public_report --kind training \
  --source runs/qlora-judgment-v1/metrics.json \
  --output reports/public/qlora-training.json
```

최신 API 보고서는 현재 prompt_version과 dataset_split을 확인한 뒤 --kind api로 선별합니다. 파일명만 보고 가장 최신이라는 가정을 하지 않습니다. 원본 보고서와 학습 결과는 비공개 백업에 보존합니다. 보고서를 공개한 뒤 새 질문군의 독립 평가를 확대할 예정이며 아직 그 결과는 없습니다.
