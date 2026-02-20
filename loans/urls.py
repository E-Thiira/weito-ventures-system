from django.urls import path

from .views import (
    ClientLoanSummaryView,
    ClientPaymentHistoryView,
    DailyCollectionsReportView,
    LoanApprovalView,
    MonthlyPerformanceReportView,
    MpesaSTKPushView,
    OutstandingLoansReportView,
    OverdueLoansReportView,
    health_check,
    mpesa_callback,
    request_client_otp,
    verify_client_otp,
)

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("client/auth/request-otp/", request_client_otp, name="client-request-otp"),
    path("client/auth/verify-otp/", verify_client_otp, name="client-verify-otp"),
    path("client/loans/summary/", ClientLoanSummaryView.as_view(), name="client-loan-summary"),
    path("client/payments/history/", ClientPaymentHistoryView.as_view(), name="client-payment-history"),
    path("mpesa/stk-push/", MpesaSTKPushView.as_view(), name="mpesa-stk-push"),
    path("mpesa/callback/<str:token>/<int:loan_id>/", mpesa_callback, name="mpesa-callback"),
    path("loans/<int:loan_id>/approve/", LoanApprovalView.as_view(), name="loan-approve"),
    path("reports/daily-collections/", DailyCollectionsReportView.as_view(), name="report-daily-collections"),
    path("reports/outstanding-loans/", OutstandingLoansReportView.as_view(), name="report-outstanding-loans"),
    path("reports/overdue-loans/", OverdueLoansReportView.as_view(), name="report-overdue-loans"),
    path("reports/monthly-performance/", MonthlyPerformanceReportView.as_view(), name="report-monthly-performance"),
]
