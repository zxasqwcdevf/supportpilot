# 기본 모델과 QLoRA의 validation 비교

## 평가기 1.2와 explicit-v3 실험

false 판정은 최소 JSON 또는 일관된 전체 빈 필드 형식을 허용합니다. answerability 전체 형식은 needs_user_facts=false, supporting_ids=[], missing_fields=[]이어야 합니다. direct_evidence 전체 형식은 snippet_ids=[]이어야 합니다. 모순되는 값, 알 수 없는 필드, 부분적으로만 추가한 필드는 실패합니다. `canonical_format`은 최소 false 형식 여부를 별도로 기록하며 전체 통과에 포함하지 않습니다. 이는 의미 판정과 직렬화 스타일을 구분하기 위한 일반 규칙입니다.

사용자가 제공한 explicit-v2 실패 출력에 이 규칙을 적용하면 base의 두 false 응답이 통과로 바뀌므로 base 15/16, adapter 14/16입니다. 실제 saved 보고서 재채점은 아래 명령으로 수행하고 원본과 evaluator version을 함께 보존합니다.

```bash
python -m scripts.rescore_qlora --report reports/qlora-comparison-1791634119483518310.json
python -m scripts.compare_qlora --correct-refund-reference --prompt-profile explicit-v3
```

explicit-v3는 질문의 대상과 요구 속성을 함께 대조하도록 합니다. 다른 대상의 요금이나 일반적인 차액 청구를 해당 상품 가격의 근거로 취급하지 않습니다. 특정 validation ID를 하드코딩하거나 모델의 잘못된 true를 false로 강제 변환하지 않습니다. 두 조건에 동일한 프롬프트를 적용하며 새 질문/새 split으로 성능을 확인한 것은 아닙니다. 반복한 validation은 개발용 결과이며 test는 계속 보류합니다. 재학습과 운영 API 변경은 하지 않았습니다.

`scripts/compare_qlora.py`는 학습에 사용한 저장 tokenizer와 정확한 기본 모델 commit을 사용합니다. NF4로 기본 모델을 한 번 로딩하고 PEFT의 `disable_adapter()`로 base 추론, adapter 활성화로 학습 모델 추론을 비교합니다. 두 조건의 입력과 생성 설정은 동일합니다. 두 모델을 동시에 로딩하지 않습니다. 이 비교는 BF16 운영 모델과 NF4 학습 모델의 비교가 아니라 동일한 NF4 base에서 adapter의 차이를 보는 실험입니다.

실행:

```bash
cd ~/projects/supportpilot
source .venv-train/bin/activate
python -m unittest tests.test_judgment_eval -v
python -m scripts.compare_qlora --dry-run
# GPU 모델 서버를 해당 터미널에서 Ctrl+C로 종료한 뒤 실행
python -m scripts.compare_qlora
```

기본 run은 `runs/qlora-judgment-v1`입니다. 다른 학습 결과는 `--run 경로`로 지정합니다. train/validation 파일 SHA를 학습 당시 기록과 비교하고, validation 레코드와 라벨을 검사합니다. test 파일은 열지 않습니다. 길이는 자르지 않습니다. 각 조건에 validation 첫 사례로 warmup 1회 후, seed로 섞은 같은 사례를 두 조건에서 순서 교대하여 생성합니다. 정답 메시지는 모델 입력에서 제거합니다. max-new-tokens 기본값은 192이며 EOS 이전에 한도에 도달하면 평가 실패입니다.

`reports/qlora-comparison-*.json`에 원문 출력, 정답, 파싱 결과, 검사별 결과와 시간이 저장됩니다. 지표:

- json_object: 순수 JSON 객체 또는 전체 JSON 코드 블록을 읽을 수 있는지. 중복 key는 실패.
- schema: 태스크별 필드·엄격한 boolean·ID 출처·필드 일관성·중복 ID·출력 종료 여부 검사.
- decision: schema를 통과한 경우에만 정답 boolean과 비교. 잘못된 JSON을 정답 false로 취급하지 않음.
- reference_ids: 정답이 true인 레코드에서 정책/구간 ID 집합의 완전 일치. 순서는 무시. 정답 false 레코드는 이 지표 분모에 포함하지 않음.
- user_facts: answerability 정답 true에서 추가 정보 필요 여부와 missing_fields 집합 비교.
- passed: 해당 레코드의 모든 검사 통과. improved/regressed는 동일 ID의 전체 통과 여부 변화.
- tp/tn/fp/fn/invalid: 태스크별 혼동 집계. schema 실패는 invalid로 따로 집계.

시간은 CUDA synchronize를 사용하며 생성 및 decode를 포함합니다. 토큰화·모델 로딩·입력 GPU 전송은 제외합니다. ID별 1회 측정이므로 운영 latency 지표로 주장하지 않습니다. base 조건에서도 비활성 adapter 가중치가 메모리에 남아 있으므로 두 모델의 개별 VRAM 비교가 아닙니다.

현재 validation은 16개 레코드이지만 같은 질문군의 변형과 두 태스크가 상관되어 있습니다. 그룹 수는 manifest/report에서 확인해야 하며 16개의 독립 질문으로 해석하지 않습니다. 이 validation은 이미 checkpoint 선택에도 사용되었습니다. 정확한 ID 일치가 실패한 다른 근거도 의미상 타당할 수 있으므로 사례별 검토가 필요합니다. 자동 label 수정이나 배포는 하지 않습니다. 같은 입력의 비교 결과를 확보한 뒤 실제 서비스 prompt 및 답변 생성 회귀를 추가 검증합니다. 최종 설정이 확정될 때까지 test를 보류합니다.

공식 근거: [PEFT disable_adapter](https://huggingface.co/docs/peft/package_reference/peft_model#peft.PeftModel.disable_adapter), [Transformers generation](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/text_generation).
