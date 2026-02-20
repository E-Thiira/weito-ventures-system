import axios from "axios";

const API_BASE_URL =
  import.meta?.env?.VITE_API_BASE_URL ||
  process.env.REACT_APP_API_BASE_URL ||
  "http://127.0.0.1:8000/api";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

export const requestOtp = (phone_number) =>
  api.post("/client/auth/request-otp/", { phone_number });
export const verifyOtp = (phone_number, otp) =>
  api.post("/client/auth/verify-otp/", { phone_number, otp });

export const applyLoan = (token, payload) =>
  api.post("/client/loans/apply/", payload, {
    headers: { Authorization: `Bearer ${token}` },
  });

export const getLoanSummary = (token) =>
  api.get("/client/loans/summary/", {
    headers: { Authorization: `Bearer ${token}` },
  });

export const getPaymentHistory = (token) =>
  api.get("/client/payments/history/", {
    headers: { Authorization: `Bearer ${token}` },
  });

export const triggerStkPush = (payload) =>
  api.post("/mpesa/stk-push/", payload);
