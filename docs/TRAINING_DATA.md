# 학습 데이터 준비 v1

## 현재 상태

검수 대기 후보 160개: 20개 질문 가족 × 표현 변형 4개 × 판정 태스크 2개.
실제 서로 다른 질문은 80개이며 템플릿 접두/접미 변형이 많습니다. 160개의 독립 사례나 검수된 학습셋으로 주장하지 않습니다.
정책 존재 판정(answerability)과 직접 구간 선택(direct_evidence)을 학습 대상으로 정했습니다.
고객지원 정책 지식을 모델에 암기시키는 답변 학습이 아니라, 제공된 문서에 대한 판정 행동을 개선하는 실험입니다.
생성된 target은 현재 가상 정책을 기반으로 프로그램이 작성한 초안입니다. 실제 검수가 끝나기 전에는 export하지 않습니다.
현재 검수 완료 0건, 학습 실행 0회입니다. 1000건 목표를 충족하지 않았습니다.

## 검수 기준

각 가족에 속한 8개 행을 모두 읽습니다. 정책의 기능/속성에 직접 답할 수 있는지, 지원 ID와 구간이 맞는지 확인합니다.
표현 변형이나 태스크가 바뀌어도 정답이 유지되는지 확인합니다. 필요 이상 구간이 선택되면 target의 snippet_ids를 줄입니다.
수정은 candidates.jsonl에서 하고 그 가족을 다시 검수합니다. 검수 이후 내용이 달라지면 sha 검사로 분할을 차단합니다.
실제 이름 대신 검수자 식별자를 사용할 수 있습니다. review 명령은 사용자가 해당 가족을 읽고 검수했음을 기록하는 동작입니다.
accepted를 일괄 자동 부여하는 명령은 제공하지 않습니다.

## WSL 준비

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/tests" .
mkdir -p data/training
cp "$SRC/data/training/candidates.jsonl" data/training/
python -m scripts.training_data inspect
python -m scripts.training_data inspect --group family-00
```

다음은 실제 검수를 마친 가족에만 실행합니다:

```bash
python -m scripts.training_data review --group family-00 --decision accepted --reviewer reviewer-01 --note '정책과 두 태스크의 라벨 확인'
```

잘못된 가족은 rejected로 기록하고 수정 후 다시 검수합니다.
data/training/reviews.json은 사람이 입력한 검수 이력입니다. 후보를 재복사해 수정 내용을 덮어쓰지 마세요.
family-00~09는 정책 있음, family-10~19는 정책 없음 초안입니다. 실제 검수로 적합성을 확인해야 합니다.

## 분할/내보내기

정책 있음/없음 각각 최소 5개의 검수된 가족이 있어야 분할할 수 있습니다.
형제 표현과 두 태스크를 같은 split에 넣고, class별 약80/10/10 비율로 고정 seed 분할합니다.
작은 데이터는 최소1가족씩 validation/test에 배치하므로 정확히80/10/10이 아닐 수 있습니다.
20가족 모두 accepted이면 train128/validation16/test16입니다.

```bash
python -m scripts.training_data split
```

prepared/train.jsonl, validation.jsonl, test.jsonl은 messages 형태입니다. manifest에는 원본/검수 hash와 가족별 분할이 있습니다.
기존 prepared가 있으면 덮어쓰지 않습니다. 다음 데이터 버전은 별도 폴더로 관리해야 합니다.
정확히 같은 질문과 family_id 분할 누수는 검사하지만 의미가 비슷한 서로 다른 가족의 누수를 완전히 자동 검출하지는 못합니다.
최종 독립 테스트셋과 분리해 관리하며 기존 24문항은 이미 개선에 사용한 회귀셋입니다.

## 1000건으로 확장하기 전에

지금 160개를 단순 복제해 1000건으로 늘리지 않습니다. 실제 조건 부족, 반박 가능 질문, 공격 지시, 유사 상품의 다른 속성을 새로운 가족으로 추가합니다.
가족 단위 검수/분할을 유지하고, 고정된 새로운 테스트 질문을 학습 데이터에 넣지 않습니다.
현재 messages의 system prompt는 런타임의 긴 prompt를 간결하게 요약한 학습 prompt입니다. 학습 후 반드시 실제 런타임 prompt로 평가해 분포 차이를 확인합니다.
QLoRA는 검수 데이터와 split이 준비된 뒤 진행합니다. 기존 v2.3/vLLM 운영 모델은 그대로 유지합니다.
