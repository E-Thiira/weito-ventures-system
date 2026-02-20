from decimal import Decimal

from rest_framework import serializers

from loans.models import Loan, Payment


class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)


class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    otp = serializers.CharField(min_length=4, max_length=10)


class ClientLoanSummarySerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Loan
        fields = ["id", "amount", "status", "due_date", "created_at", "balance", "approval_status"]


class PaymentHistorySerializer(serializers.ModelSerializer):
    loan_id = serializers.IntegerField(source="loan.id", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "loan_id", "amount", "mpesa_receipt", "phone", "paid_at"]


class LoanApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["APPROVE", "REJECT"])


class HealthCheckResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()


class GenericMessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


class OTPRequestResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    otp_id = serializers.IntegerField()


class OTPVerifyResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class MpesaCallbackAckSerializer(serializers.Serializer):
    ResultCode = serializers.IntegerField()
    ResultDesc = serializers.CharField()


class DailyCollectionsSerializer(serializers.Serializer):
    date = serializers.DateField()
    total_collections = serializers.DecimalField(max_digits=12, decimal_places=2)
    payments_count = serializers.IntegerField()


class OutstandingLoansSerializer(serializers.Serializer):
    outstanding_loans_count = serializers.IntegerField()
    outstanding_total = serializers.DecimalField(max_digits=12, decimal_places=2)


class OverdueLoansSerializer(serializers.Serializer):
    overdue_count = serializers.IntegerField()
    results = ClientLoanSummarySerializer(many=True)


class MonthlyPerformanceSerializer(serializers.Serializer):
    month_start = serializers.DateField()
    as_of = serializers.DateField()
    collections = serializers.DictField()
    loans = serializers.DictField()


class STKPushSerializer(serializers.Serializer):
    loan_id = serializers.IntegerField()
    phone = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate(self, attrs):
        loan = Loan.objects.filter(id=attrs["loan_id"]).select_related("client").first()
        if loan is None:
            raise serializers.ValidationError("Loan not found")
        if attrs["amount"] <= Decimal("0"):
            raise serializers.ValidationError("Amount must be greater than zero")
        if attrs["amount"] > loan.balance:
            raise serializers.ValidationError("Amount cannot exceed outstanding balance")
        attrs["loan"] = loan
        return attrs


class ClientLoanApplicationSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    due_date = serializers.DateField()

    def validate(self, attrs):
        request = self.context["request"]
        client = request.user
        if attrs["amount"] <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        if attrs["amount"] > client.max_loan_limit:
            raise serializers.ValidationError(
                f"Requested amount exceeds your limit ({client.max_loan_limit})."
            )
        return attrs
