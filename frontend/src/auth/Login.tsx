import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";

export default function Login() {
  const navigate = useNavigate();
  const { session, sendOtp, verifyOtp } = useAuth();

  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [loading, setLoading] = useState<"send" | "verify" | null>(null);
  const [error, setError] = useState<string>("");
  const [message, setMessage] = useState<string>("");

  if (session) {
    return <Navigate to="/dashboard" replace />;
  }

  async function onSendOtp() {
    setError("");
    setMessage("");
    setLoading("send");
    try {
      await sendOtp(email.trim());
      setOtpSent(true);
      setMessage("OTP sent. Check your email inbox.");
    } catch (err) {
      const nextError = err instanceof Error ? err.message : "Unable to send OTP";
      setError(nextError);
    } finally {
      setLoading(null);
    }
  }

  async function onVerifyOtp() {
    setError("");
    setMessage("");
    setLoading("verify");
    try {
      await verifyOtp(email.trim(), otp.trim());
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const nextError = err instanceof Error ? err.message : "Invalid OTP";
      setError(nextError);
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>Sign In to OptionLens</h2>
        <p>Use your email OTP to continue.</p>

        <label className="auth-field">
          <span>Email</span>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading !== null}
          />
        </label>

        <button
          type="button"
          className="auth-button"
          onClick={onSendOtp}
          disabled={loading !== null || !email.trim()}
        >
          {loading === "send" ? "Sending OTP..." : otpSent ? "Resend OTP" : "Send OTP"}
        </button>

        {otpSent ? (
          <>
            <label className="auth-field">
              <span>OTP (6 digits)</span>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="123456"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                disabled={loading !== null}
              />
            </label>
            <button
              type="button"
              className="auth-button secondary"
              onClick={onVerifyOtp}
              disabled={loading !== null || otp.trim().length !== 6}
            >
              {loading === "verify" ? "Verifying..." : "Verify OTP"}
            </button>
          </>
        ) : null}

        {message ? <div className="auth-message">{message}</div> : null}
        {error ? <div className="auth-error">{error}</div> : null}
      </div>
    </div>
  );
}
