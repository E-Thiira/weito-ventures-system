# Weito Ventures API Documentation

Interactive docs are auto-generated with DRF Spectacular:

- Swagger UI: `/api/docs/`
- OpenAPI schema JSON: `/api/schema/`

## Included endpoint groups

### Loan endpoints

- `POST /api/loans/{loan_id}/approve/` (loan officer role)
- `GET /api/client/loans/summary/` (client portal)
- `GET /api/reports/outstanding-loans/`
- `GET /api/reports/overdue-loans/`

### Payment callbacks

- `POST /api/mpesa/stk-push/`
- `POST /api/mpesa/callback/{token}/{loan_id}/`

### SMS/notification triggers

- `POST /api/client/auth/request-otp/` (sends OTP notification)
- Payment confirmation and reminders are triggered by background tasks:
  - `loans.tasks.send_payment_confirmation_sms`
  - `loans.tasks.send_due_soon_reminders`
  - `loans.tasks.send_overdue_reminders`

Use Swagger UI to test endpoint payloads and responses directly.
