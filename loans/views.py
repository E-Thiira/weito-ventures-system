import hashlib
import hmac
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ClientTokenAuthentication
from .models import Client, ClientAccessToken, ClientOTP, Loan, Payment, SuspiciousActivityLog
from .permissions import IsClientAuthenticated, IsLoanOfficer
from .serializers import (
    ClientLoanSummarySerializer,
    ClientLoanApplicationSerializer,
    DailyCollectionsSerializer,
    HealthCheckResponseSerializer,
    LoanApprovalSerializer,
    MonthlyPerformanceSerializer,
    MpesaCallbackAckSerializer,
    OTPRequestSerializer,
    OTPRequestResponseSerializer,
    OTPVerifyResponseSerializer,
    OTPVerifySerializer,
    OutstandingLoansSerializer,
    OverdueLoansSerializer,
    PaymentHistorySerializer,
    STKPushSerializer,
)
from .services.mpesa import MpesaService
from .services.sms import send_with_fallback


@extend_schema(responses=HealthCheckResponseSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
async def health_check(request):
    return Response({"status": "ok", "service": "weito_backend"})


class MpesaSTKPushView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [AllowAny]

    @extend_schema(request=STKPushSerializer, responses=dict)
    def post(self, request):
        serializer = STKPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = serializer.validated_data["loan"]
        phone = serializer.validated_data["phone"]
        amount = serializer.validated_data["amount"]

        if loan.status == Loan.Status.PAID:
            return Response({"detail": "Loan already paid."}, status=status.HTTP_400_BAD_REQUEST)

        callback_url = (
            f"{settings.MPESA_CALLBACK_BASE_URL.rstrip('/')}"
            f"/api/mpesa/callback/{settings.MPESA_CALLBACK_TOKEN}/{loan.id}/"
        )

        result = MpesaService().stk_push(
            phone=phone,
            amount=amount,
            account_reference=f"LOAN-{loan.id}",
            transaction_desc=f"Loan repayment {loan.id}",
            callback_url=callback_url,
        )
        return Response(result)


@extend_schema(request=dict, responses=MpesaCallbackAckSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
def mpesa_callback(request, token: str, loan_id: int):
    if not secrets.compare_digest(token, settings.MPESA_CALLBACK_TOKEN):
        return Response({"detail": "Unauthorized callback."}, status=status.HTTP_403_FORBIDDEN)

    if settings.MPESA_WEBHOOK_SECRET:
        signature = request.headers.get("X-Callback-Signature", "")
        computed = hmac.new(
            settings.MPESA_WEBHOOK_SECRET.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not signature or not secrets.compare_digest(signature, computed):
            return Response({"detail": "Invalid webhook signature."}, status=status.HTTP_403_FORBIDDEN)

    allowed_ips = settings.MPESA_CALLBACK_ALLOWED_IPS
    if allowed_ips:
        remote_ip = request.META.get("REMOTE_ADDR", "")
        if remote_ip not in allowed_ips:
            return Response({"detail": "Forbidden source."}, status=status.HTTP_403_FORBIDDEN)

    payload = request.data or {}
    stk_callback = payload.get("Body", {}).get("stkCallback", {})
    if stk_callback.get("ResultCode") != 0:
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    loan = Loan.objects.filter(id=loan_id).first()
    if not loan:
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
    metadata = {item.get("Name"): item.get("Value") for item in metadata_items if item.get("Name")}
    amount = metadata.get("Amount")
    mpesa_receipt = metadata.get("MpesaReceiptNumber")
    phone = str(metadata.get("PhoneNumber") or loan.client.phone_number)

    if not mpesa_receipt or amount is None:
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    try:
        amount_decimal = Decimal(str(amount))
    except Exception:
        SuspiciousActivityLog.objects.create(
            category="INVALID_AMOUNT",
            reference=f"loan:{loan.id}",
            severity="HIGH",
            details={"amount": amount, "receipt": mpesa_receipt},
        )
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    if amount_decimal <= 0:
        SuspiciousActivityLog.objects.create(
            category="NON_POSITIVE_AMOUNT",
            reference=f"loan:{loan.id}",
            severity="HIGH",
            details={"amount": str(amount_decimal), "receipt": mpesa_receipt},
        )
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    if amount_decimal > loan.balance:
        SuspiciousActivityLog.objects.create(
            category="OVERPAYMENT_ATTEMPT",
            reference=f"loan:{loan.id}",
            severity="HIGH",
            details={"amount": str(amount_decimal), "balance": str(loan.balance), "receipt": mpesa_receipt},
        )
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    if Payment.objects.filter(mpesa_receipt=mpesa_receipt).exists():
        SuspiciousActivityLog.objects.get_or_create(
            category="DUPLICATE_RECEIPT",
            reference=mpesa_receipt,
            defaults={"severity": "MEDIUM", "details": {"loan_id": loan.id}},
        )
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    try:
        Payment.objects.create(
            loan=loan,
            amount=amount_decimal,
            mpesa_receipt=mpesa_receipt,
            phone=phone,
            raw_payload=payload,
        )
    except IntegrityError:
        pass

    return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


@extend_schema(request=OTPRequestSerializer, responses=OTPRequestResponseSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
def request_client_otp(request):
    serializer = OTPRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone_number = serializer.validated_data["phone_number"]

    client = Client.objects.filter(phone_number=phone_number).first()
    if not client:
        return Response({"detail": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    otp_record, otp = ClientOTP.issue_for_phone(phone_number)
    send_with_fallback(phone_number, f"Your verification code is {otp}. It expires in 5 minutes.")
    return Response({"detail": "OTP sent", "otp_id": otp_record.id})


@extend_schema(request=OTPVerifySerializer, responses=OTPVerifyResponseSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_client_otp(request):
    serializer = OTPVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone_number = serializer.validated_data["phone_number"]
    otp = serializer.validated_data["otp"]

    otp_record = ClientOTP.objects.filter(phone_number=phone_number).order_by("-created_at").first()
    if not otp_record or not otp_record.verify(otp):
        return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

    client = Client.objects.filter(phone_number=phone_number).first()
    if not client:
        return Response({"detail": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    token_obj, raw_token = ClientAccessToken.create_token(client)
    return Response({"access_token": raw_token, "expires_at": token_obj.expires_at})


class ClientLoanSummaryView(APIView):
    authentication_classes = [ClientTokenAuthentication]
    permission_classes = [IsClientAuthenticated]

    @extend_schema(responses=dict)
    def get(self, request):
        loans = Loan.objects.filter(client=request.user).order_by("-created_at")
        serialized = ClientLoanSummarySerializer(loans, many=True)
        return Response(
            {
                "client": {
                    "name": request.user.name,
                    "phone_number": request.user.phone_number,
                    "credit_score": request.user.credit_score,
                    "max_loan_limit": request.user.max_loan_limit,
                },
                "loans": serialized.data,
            }
        )


class ClientPaymentHistoryView(APIView):
    authentication_classes = [ClientTokenAuthentication]
    permission_classes = [IsClientAuthenticated]

    @extend_schema(responses=PaymentHistorySerializer(many=True))
    def get(self, request):
        payments = Payment.objects.filter(loan__client=request.user).select_related("loan").order_by("-paid_at")
        serialized = PaymentHistorySerializer(payments, many=True)
        return Response({"results": serialized.data})


class ClientLoanApplicationView(APIView):
    authentication_classes = [ClientTokenAuthentication]
    permission_classes = [IsClientAuthenticated]

    @extend_schema(request=ClientLoanApplicationSerializer, responses=dict)
    def post(self, request):
        serializer = ClientLoanApplicationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        loan = Loan.objects.create(
            client=request.user,
            amount=serializer.validated_data["amount"],
            due_date=serializer.validated_data["due_date"],
            approval_status=Loan.ApprovalStatus.PENDING,
        )
        return Response(
            {
                "loan_id": loan.id,
                "status": loan.status,
                "approval_status": loan.approval_status,
                "amount": loan.amount,
                "due_date": loan.due_date,
            },
            status=status.HTTP_201_CREATED,
        )


class LoanApprovalView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated, IsLoanOfficer]

    @extend_schema(request=LoanApprovalSerializer, responses=dict)
    def post(self, request, loan_id: int):
        serializer = LoanApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        loan = Loan.objects.select_related("client").filter(id=loan_id).first()
        if not loan:
            return Response({"detail": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

        if action == "APPROVE":
            if loan.amount > loan.client.max_loan_limit:
                return Response(
                    {"detail": f"Loan amount exceeds client limit. Max allowed is {loan.client.max_loan_limit}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            loan.approval_status = Loan.ApprovalStatus.APPROVED
        else:
            loan.approval_status = Loan.ApprovalStatus.REJECTED

        loan.approved_by = request.user
        loan.approved_at = timezone.now()
        loan.save(update_fields=["approval_status", "approved_by", "approved_at", "status"])
        return Response(
            {
                "loan_id": loan.id,
                "approval_status": loan.approval_status,
                "approved_by": str(request.user),
                "approved_at": loan.approved_at,
            }
        )


@method_decorator(cache_page(60 * 5), name="dispatch")
class DailyCollectionsReportView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DailyCollectionsSerializer)
    def get(self, request):
        today = timezone.localdate()
        payments = Payment.objects.filter(paid_at__date=today)
        total = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        return Response({"date": today, "total_collections": total, "payments_count": payments.count()})


@method_decorator(cache_page(60 * 5), name="dispatch")
class OutstandingLoansReportView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OutstandingLoansSerializer)
    def get(self, request):
        loans = Loan.objects.exclude(status=Loan.Status.PAID)
        outstanding_total = Decimal("0.00")
        for loan in loans:
            outstanding_total += loan.balance
        return Response({"outstanding_loans_count": loans.count(), "outstanding_total": outstanding_total})


@method_decorator(cache_page(60 * 5), name="dispatch")
class OverdueLoansReportView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OverdueLoansSerializer)
    def get(self, request):
        today = timezone.localdate()
        overdue_loans = Loan.objects.filter(due_date__lt=today).exclude(status=Loan.Status.PAID)
        return Response({"overdue_count": overdue_loans.count(), "results": ClientLoanSummarySerializer(overdue_loans, many=True).data})


@method_decorator(cache_page(60 * 5), name="dispatch")
class MonthlyPerformanceReportView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MonthlyPerformanceSerializer)
    def get(self, request):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        monthly_payments = Payment.objects.filter(paid_at__date__gte=month_start, paid_at__date__lte=today)
        monthly_total = monthly_payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        loan_summary = Loan.objects.aggregate(
            total_loans=Count("id"),
            paid_loans=Count("id", filter=Q(status=Loan.Status.PAID)),
            overdue_loans=Count("id", filter=Q(status=Loan.Status.OVERDUE)),
        )

        return Response(
            {
                "month_start": month_start,
                "as_of": today,
                "collections": {"total": monthly_total, "payments_count": monthly_payments.count()},
                "loans": loan_summary,
            }
        )
