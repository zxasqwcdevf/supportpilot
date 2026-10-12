# 검색 실험 v1

가상 정책 10개와 개발 질문 14개(관련 문서 있음 12개, 없음 2개)를 추가했습니다.
keyword: 기존 명시 키워드 일치. bm25: 제목·키워드·본문의 BM25와 한국어 문자 bigram.
hybrid: BM25와 multilingual-e5-small CPU 임베딩 검색을 RRF로 결합합니다. 문서 벡터는 프로세스 내 캐시합니다.
E5 입력은 query:/passage: 접두어를 사용하며 임베딩은 정규화합니다.
접두어 설정 근거: [E5 공식 모델 카드](https://huggingface.co/intfloat/multilingual-e5-small).
GPU 메모리를 추가 점유하지 않도록 임베딩은 CPU로 실행합니다. 첫 실행은 다운로드·인코딩 시간이 포함됩니다.

## 로컬 실측

| 방식 | Recall@3 (12개) | MRR@3 | 문서 없는 질문 보류 (2개) |
|---|---:|---:|---:|
| keyword | 0.625 | 0.667 | 1.0 |
| bm25 (v1) | 1.0 | 0.958 | 0.0 |
| bm25 (v2, 개발 cutoff 적용) | 1.0 | 0.958 | 1.0 |

BM25는 재현율을 개선하지만 일반 단어의 일치만으로 무관 문서를 반환할 수 있습니다.
기본 API 검색은 keyword로 유지했습니다. v2는 최종 후보별로 BM25>=2.0 또는 dense>=0.8을 요구합니다.
Dense cutoff 0.8은 개발 시작값이며 신뢰 확률이 아닙니다. 별도 검증셋으로 cutoff와 답변 보류 기준을 보정해야 합니다.
현재 정책은 모두 최신 버전이며 정책 충돌/적용기간 필터는 아직 구현하지 않았습니다.
임베딩 실행은 이 Windows 세션에서 확인하지 않았습니다. 결합 로직은 주입한 점수로 테스트했습니다.

## WSL 검색 비교

```bash
cd ~/projects/supportpilot
source .venv/bin/activate
SRC=/mnt/c/Users/user/Documents/Codex/2026-10-09/new-chat-2/outputs/supportpilot
cp -r "$SRC/supportpilot" "$SRC/scripts" "$SRC/data" "$SRC/tests" .
pip install 'sentence-transformers>=3,<6'
python -m unittest discover -s tests -p test_retrieval.py -v
python -m scripts.evaluate_retrieval --methods keyword bm25 hybrid
```

reports/retrieval-*.json에 질문별 순위·점수·평가 결과가 저장됩니다.
BM25/임베딩 도입 효과는 모델 답변 품질과 별개이므로 검색 지표와 모델 평가를 함께 확인하세요.

## 하이브리드 API 실험

8018 API를 중지한 터미널에서만 다음을 실행합니다. 모델 서버는 그대로 둡니다.

```bash
export SUPPORTPILOT_RETRIEVAL=hybrid
export SUPPORTPILOT_MODEL_URL=http://127.0.0.1:8081/v1
python -m uvicorn supportpilot.api:app --host 127.0.0.1 --port 8018
```

다른 터미널에서 회귀 평가:

```bash
python -m scripts.benchmark --suite model --url http://127.0.0.1:8018
```

unknown-feature가 실패할 수 있습니다. 검색 방식 변경으로 관련성 판정과 보류가 악화됐음을 보여주는 회귀 사례이며 통과하도록 기대값을 바꾸지 않습니다.
v2에서 기존 음성 사례는 낮은 BM25 점수로 인해 제외될 것으로 기대하지만, 새 음성 사례에 대한 보류를 보장하지 않습니다.
원복: API 중지 → `export SUPPORTPILOT_RETRIEVAL=keyword` → API 재실행.
다음 작업은 독립된 양성·음성 질문을 추가해 검색 점수 기반 보류 기준을 평가하는 것입니다.

## v2 변경 사항

- keyword는 단어 경계와 제한된 한국어 조사/요청 어미를 사용해 프로젝트/프로 오탐을 제거합니다. 형태소 분석기가 아니므로 일부 복합어·표현은 놓칠 수 있습니다.
- 최종 후보에도 관련성 gate를 적용해 BM25-only 결과가 dense cutoff를 우회하는 문제를 해결합니다. BM25 cutoff는 환경변수 SUPPORTPILOT_BM25_THRESHOLD, dense cutoff는 SUPPORTPILOT_DENSE_THRESHOLD로 조절합니다.
- cutoff 2.0/0.8은 이미 확인한 개발 사례를 참고한 후보값입니다. 현재 개발셋 통과율을 독립 검증 결과로 주장하지 않습니다.
- RRF 점수는 소수 12자리로 동점 판정한 후 dense 점수, BM25 점수, 문서 ID 순서로 정렬합니다.
- 평가기는 hybrid 모델 로딩/문서·워밍업 인코딩 시간을 initialization_ms로 별도 측정하며 이후 warm_p50_ms/warm_p95_ms를 기록합니다. 다운로드·로딩·인코딩 각각의 시간은 분리하지 않습니다.
- 첫 API 요청의 초기화 시간은 평가기 워밍업과 별개입니다. 평가 도구에서 워밍업했다고 다른 API 프로세스가 초기화되지는 않습니다.
- 이전 보고서는 보존하고 retrieval_version=2.0과 기록된 cutoff를 함께 비교하세요.
