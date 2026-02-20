from decimal import Decimal

from django.db.models import F, Max, Sum

from loans.models import Client, Loan


def recompute_client_credit(client: Client) -> Client:
    loans = client.loans.all()
    total_loans = loans.count()
    if total_loans == 0:
        client.credit_score = 0
        client.max_loan_limit = Decimal("5000.00")
        client.save(update_fields=["credit_score", "max_loan_limit", "updated_at"])
        return client

    paid_count = loans.filter(status=Loan.Status.PAID).count()

    paid_loans_with_last_payment = loans.filter(status=Loan.Status.PAID).annotate(last_paid_at=Max("payments__paid_at"))
    on_time_paid = paid_loans_with_last_payment.filter(last_paid_at__date__lte=F("due_date")).count()

    aggregate = loans.aggregate(total_due=Sum("amount"), total_paid=Sum("payments__amount"))
    total_due = aggregate["total_due"] or Decimal("0.00")
    total_paid = aggregate["total_paid"] or Decimal("0.00")

    completion_rate = paid_count / total_loans
    timeliness_rate = (on_time_paid / paid_count) if paid_count else 0
    repayment_ratio = float(min(Decimal("1.0"), (total_paid / total_due) if total_due else Decimal("0.0")))

    score = int((completion_rate * 40) + (timeliness_rate * 40) + (repayment_ratio * 20))
    score = max(0, min(100, score))

    base_limit = Decimal("5000.00")
    multiplier = Decimal("1.0") + (Decimal(score) / Decimal("100"))
    max_limit = (base_limit * multiplier).quantize(Decimal("0.01"))

    client.credit_score = score
    client.max_loan_limit = max_limit
    client.save(update_fields=["credit_score", "max_loan_limit", "updated_at"])
    return client
