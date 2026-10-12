# 기획·설계 v0.1

## 목표와 범위

사용자는 상담원. 제품 정책에 근거한 답변 초안을 제공하고 상담원의 확인을 지원한다.
핵심 연구 질문: 단일 16GB GPU에서 한국어 고객지원의 품질과 답변 보류 능력을 확보하면서 추론 자원을 줄일 수 있는가?
MVP: 정책 검색, 출처 인용, 답변 보류, 재현 가능한 평가. 이후 추가 질문, 분류, 상담원 승인.
실제 고객정보, 결제 실행, 외부 서비스 연동은 초기 범위에서 제외.

## 모델 실험

주력 Qwen3-4B-Instruct-2507. BF16 기준선 → 4비트 배포 후보 → QLoRA.
Qwen3-8B 4비트는 배포 후보 비교군. 모델 크기만의 인과 비교로 해석하지 않는다.
추론 입력+출력 4096토큰, 출력 최대 512토큰, 동시 요청 1부터 측정.
학습 길이 2048, micro batch 1, accumulation 8, rank 16, gradient checkpointing부터 시작.
메모리 수치는 실측 전 확정하지 않는다. 학습 중 서빙 프로세스 종료.

## 데이터

정책 문서 30~50개, 검수 학습 사례 1000~2000개 목표.
질문 유형: 일반, 조건부, 정보 부족, 답변 불가, 정책 충돌, 공격 입력.
동일 원본 문의·표현 변형은 한 분할에만 포함. validation에서 튜닝하고 최종 test 200개는 고정한다.
모델 생성 데이터는 출처·생성 모델·검수 여부 기록. 정답은 정책 근거와 사람이 확인한다.

## 아키텍처

Next.js → FastAPI → 분류 → PostgreSQL/pgvector+키워드 검색 → reranker → 모델 → 스키마·인용 검증 → 초안/추가질문/보류 → 승인.
엔티티: Document(id,version,effective_from,product,text), Chunk(document_id,span), Run(model_revision,prompt_version,retrieval_ids,latency,status), Review(run_id,decision,edited_answer).
검색 문서는 명령이 아닌 데이터로 취급. 인용 ID는 검색 결과의 허용 목록으로 검증한다.
답변 생성 전 상품·날짜 조건 필터. 근거 부족·충돌은 보류하고 상담원에게 전달한다.

## 평가

검색 Recall@5/MRR, 정답·인용 정확도, 보류 precision/recall, 분류 Macro-F1, JSON 유효율.
운영 TTFT, 전체 P50/P95, GPU peak memory, 동시성별 처리량. 입력 길이·출력 길이·warmup 조건 고정.
필수 비교: 단독/RAG, 벡터/하이브리드, reranker 유무, 기본/QLoRA, BF16/양자화, 4B/8B.
현재 4개 smoke case의 통과는 모델 성능 증거가 아니다.

## 10주 작업

1. 환경 호환성·추론 기준값, 실패시 Transformers 단일 추론으로 우회
2. 요구사항·API·DB·문서와 평가셋 v1
3. 벡터 검색·모델 호출·인용 검증
4. 하이브리드·reranker 비교
5. 실패 분석·학습 데이터 검수
6. QLoRA와 학습 전후 평가
7. 양자화·8B·서빙 부하 비교
8. 최소 UI·승인·실행 이력
9. 회귀·공격·부하 테스트와 Docker/CI
10. 고정 테스트 최종 평가·보고서·데모

1주차 완료 조건: 실제 모델 20개 질문 추론 성공, peak memory와 latency 저장, 환경 버전 고정.
현재는 1주차 준비 및 검색 기준선 구현 상태. 학습·품질 결과는 아직 없음.
