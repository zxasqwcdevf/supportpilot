"""Policy decisions using explicit user-supplied facts, not inferred facts."""
from datetime import date, datetime, timedelta, timezone


def today_kst() -> date:
    return datetime.now(timezone(timedelta(hours=9))).date()


def decide(document: dict, facts: dict | None, today: date | None = None) -> dict:
    today = today or today_kst()
    facts = facts or {}
    fields = document["decision"]["required_fields"]
    missing = [field for field in fields if facts.get(field) is None]
    result = {
        "status": "needs_information", "mode": "policy_rule",
        "validation": "structured_policy_rule",
        "citations": [{"id": document["id"], "title": document["title"], "version": document["version"], "quote": document["text"]}],
        "required_fields": missing,
        "facts_source": "user_provided_unverified",
        "evaluated_on": today.isoformat(),
    }
    payment = facts.get("payment_date")
    if payment is not None:
        payment = date.fromisoformat(payment) if isinstance(payment, str) else payment
        if payment > today:
            return {**result, "answer": "결제일이 미래 날짜입니다. 실제 결제일을 확인해 주세요.", "reason": "future_payment_date", "required_fields": ["payment_date"]}
    if missing:
        labels = {"plan": "요금제(annual 또는 monthly)", "payment_date": "결제일(YYYY-MM-DD)", "usage_history": "사용 이력 여부(true 또는 false)"}
        return {**result, "answer": document["text"] + "\n\n다음 정보를 알려주세요: " + ", ".join(labels[field] for field in missing), "reason": "missing_refund_facts"}
    days = (today - payment).days
    if facts["plan"] == "annual" and days <= 7 and facts["usage_history"] is False:
        return {**result, "status": "draft", "answer": "입력하신 정보 기준으로 연간 요금제·결제 후 7일 이내·사용 이력 없음 조건을 충족하므로 전액 환불 대상입니다. 실제 처리는 상담원이 결제 정보를 확인한 후 진행합니다.", "reason": "full_refund_conditions_met", "days_since_payment": days}
    return {**result, "status": "requires_review", "answer": "입력하신 정보는 연간 요금제 전액 환불 조건에 해당하지 않거나 해당 정책의 적용 범위 밖입니다. 그 외 요청은 상담원이 결제일과 사용 이력을 확인합니다.", "reason": "manual_refund_review", "days_since_payment": days}
