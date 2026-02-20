# Frontend ↔ Backend Connection

No frontend source code exists in this workspace, so this folder provides drop-in integration assets.

## 1) Configure API base URL

- Vite: `VITE_API_BASE_URL=http://127.0.0.1:8000/api`
- CRA: `REACT_APP_API_BASE_URL=http://127.0.0.1:8000/api`

## 2) Use API client

Import `apiClient.js` functions:

- `requestOtp(phone)`
- `verifyOtp(phone, otp)`
- `applyLoan(token, { amount, due_date })`
- `triggerStkPush({ loan_id, phone, amount })`
- `getLoanSummary(token)`
- `getPaymentHistory(token)`

## 3) Typical flow

1. Client requests OTP
2. Client verifies OTP and receives access token
3. Submit loan application
4. Poll/get summary for approval + status updates
5. Trigger STK push and refresh summary/payment history
