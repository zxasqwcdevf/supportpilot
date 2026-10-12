import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from supportpilot.core import DATA
from supportpilot.generation import source_snippets
from supportpilot.training_data import digest, validate_record, messages, grouped_split

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/training/candidates.jsonl"
REVIEWS = ROOT / "data/training/reviews.json"

SEEDS = [
    ("refund-v1", "연간 상품의 전액 환불 조건을 설명해 주세요.", True),
    ("password-v1", "계정 암호를 다시 설정하는 절차를 설명해 주세요.", True),
    ("plan-v1", "Pro의 월 요금과 이용 가능한 팀원 한도를 설명해 주세요.", True),
    ("invoice-v1", "구매 영수증을 PDF 파일로 받는 경로를 설명해 주세요.", True),
    ("invite-v1", "팀 관리자가 동료를 이메일로 초대하는 절차를 설명해 주세요.", True),
    ("export-v1", "프로젝트 데이터 내보내기의 파일 형식과 제외 항목을 설명해 주세요.", True),
    ("delete-v1", "계정 제거 신청 후 취소할 수 있는 기간을 설명해 주세요.", True),
    ("incident-v1", "서비스 오류 문의에 포함해야 할 정보를 설명해 주세요.", True),
    ("change-plan-v1", "요금제 상향과 하향의 적용 시점을 설명해 주세요.", True),
    ("security-v1", "인증 앱과 복구 코드를 이용하는 방법을 설명해 주세요.", True),
    ("plan-v1", "Pro 구독의 API 요청량 상한을 알려 주세요.", False),
    ("password-v1", "등록된 이메일을 수정하는 메뉴를 알려 주세요.", False),
    ("security-v1", "SAML 기반 회사 계정 연동 절차를 알려 주세요.", False),
    ("export-v1", "첨부 자료 저장 공간을 늘리는 추가 요금을 알려 주세요.", False),
    ("invoice-v1", "외화 결제를 선택하는 설정을 알려 주세요.", False),
    ("invite-v1", "팀 대화방을 외부 메신저와 연동하는 방법을 알려 주세요.", False),
    ("incident-v1", "서비스 장애 알림의 webhook 등록 경로를 알려 주세요.", False),
    ("delete-v1", "관리자의 접속 감사 기록 보존 기간을 알려 주세요.", False),
    ("change-plan-v1", "법인 전용 상품으로 변경할 때 가격을 알려 주세요.", False),
    ("refund-v1", "연 단위 구독 구매 할인 비율을 알려 주세요.", False),
]


def read_rows():
    return [json.loads(line) for line in CANDIDATES.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding="utf-8")


def build():
    if CANDIDATES.exists():
        raise ValueError("Candidate file exists; preserve reviews instead of overwriting")
    documents = json.loads(DATA.read_text(encoding="utf-8"))
    rows = []
    for family, (doc_id, question, supported) in enumerate(SEEDS):
        index = next(i for i, doc in enumerate(documents) if doc["id"] == doc_id)
        policies = [documents[index], documents[(index+1) % len(documents)], documents[(index+3) % len(documents)]]
        for variant, text in enumerate([question, "문의드립니다. " + question, question + " 정책을 근거로 답변해 주세요.", "상담원이 안내할 내용으로 " + question]):
            for task in ["answerability", "direct_evidence"]:
                if task == "answerability":
                    target = {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": [doc_id], "missing_fields": []} if supported else {"has_answering_policy": False}
                else:
                    target = {"directly_supported": True, "snippet_ids": [s["snippet_id"] for s in source_snippets([documents[index]])]} if supported else {"directly_supported": False}
                row = {"id": f"seed-{family:02}-{variant}-{task}", "group_id": f"family-{family:02}", "task": task, "question": text, "policies": policies, "target": target, "source_kind": "template_seed", "review_status": "pending"}
                validate_record(row)
                rows.append(row)
    write_jsonl(CANDIDATES, rows)
    print(f"Created {len(rows)} pending candidates in {CANDIDATES}; NOT a reviewed training set")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "inspect", "review", "split"])
    parser.add_argument("--group")
    parser.add_argument("--decision", choices=["accepted", "rejected"])
    parser.add_argument("--reviewer")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    if args.action == "build":
        build()
        return
    rows = read_rows()
    reviews = json.loads(REVIEWS.read_text(encoding="utf-8")) if REVIEWS.exists() else {}
    groups = {row["group_id"] for row in rows}
    selected = [r for r in rows if r["group_id"] == args.group] if args.group else rows
    if args.action == "inspect":
        if args.group:
            print(json.dumps(selected, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"candidates": len(rows), "families": len(groups), "reviews": {g: receipt["decision"] for g, receipt in reviews.items()}}, ensure_ascii=False, indent=2))
        return
    if args.action == "review":
        if args.group not in groups or not args.decision or not args.reviewer or not args.reviewer.strip():
            parser.error("review requires valid --group, --decision and --reviewer")
        reviews[args.group] = {"decision": args.decision, "reviewer": args.reviewer.strip(), "group_sha256": digest(selected), "reviewed_at": datetime.now(timezone.utc).isoformat(), "note": args.note}
        REVIEWS.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved review of {args.group}: {args.decision}")
        return
    accepted = []
    for group_id, receipt in reviews.items():
        group = [r for r in rows if r["group_id"] == group_id]
        if digest(group) != receipt["group_sha256"]:
            raise ValueError("Stale review: " + group_id)
        if receipt["decision"] == "accepted":
            accepted.extend(group)
    accepted_groups = {r["group_id"] for r in accepted}
    supported = {r["group_id"] for r in accepted if r["target"].get("has_answering_policy", r["target"].get("directly_supported")) is True}
    unsupported = accepted_groups - supported
    print(f"Accepted families: {len(accepted_groups)}; supported: {len(supported)}; unsupported: {len(unsupported)}")
    try:
        splits = grouped_split(accepted)
    except ValueError as exc:
        parser.exit(2, f"분할하지 않았습니다: {exc}\n최소 정책 근거 있음 5개 그룹과 근거 없음 5개 그룹을 검수해야 합니다.\n각 그룹은 inspect --group으로 확인한 뒤 review로 기록하세요.\n")
    output = ROOT / "data/training/prepared"
    if output.exists():
        raise ValueError("Prepared split exists; preserve it and create a versioned dataset")
    for name, subset in splits.items():
        write_jsonl(output / (name + ".jsonl"), [{"id": r["id"], "group_id": r["group_id"], "task": r["task"], "messages": messages(r)} for r in subset])
    (output / "manifest.json").write_text(json.dumps({"seed": 20261010, "candidate_sha256": digest(rows), "reviews_sha256": digest(reviews), "counts": {name: len(subset) for name, subset in splits.items()}, "groups": {name: sorted({r["group_id"] for r in subset}) for name, subset in splits.items()}, "limitations": "Grouped small template seeds; not an independent domain test or 1000 reviewed examples"}, indent=2), encoding="utf-8")
    print(json.dumps({name: len(subset) for name, subset in splits.items()}, indent=2))


if __name__ == "__main__":
    main()
