import { useState } from "react";
import { Activity, ArrowRight, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

function loginErrorMessage(error) {
  if (error?.response?.status === 401) return "อีเมลหรือรหัสผ่านไม่ถูกต้อง";
  if (error?.response?.status === 422) return "กรุณาตรวจสอบรูปแบบอีเมลและรหัสผ่าน";
  if (error?.response) return "เข้าสู่ระบบไม่สำเร็จ กรุณาลองอีกครั้ง";
  return "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้ โปรดลองใหม่ภายหลัง";
}

export default function LoginPage() {
  const { user, login, isLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(location.state?.message || "");

  if (user) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      await login(email.trim(), password);
      navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
    } catch (loginError) {
      setError(loginErrorMessage(loginError));
    }
  }

  return (
    <main className="login-page">
      <div className="login-decoration decoration-one" />
      <div className="login-decoration decoration-two" />
      <section className="login-panel">
        <div className="login-brand">
          <div className="login-brand-mark"><Activity size={24} strokeWidth={2.4} /></div>
          <div>
            <span className="login-brand-name">เครือข่ายสุขภาพ</span>
            <span className="login-brand-caption">ศูนย์ปฏิบัติการเครือข่าย</span>
          </div>
        </div>

        <div className="login-heading">
          <div className="login-eyebrow">โรงพยาบาล · ระบบสารสนเทศ</div>
          <h1>ยินดีต้อนรับ</h1>
          <p>เข้าสู่ระบบเพื่อดูสถานะเครือข่ายของโรงพยาบาล</p>
        </div>

        {error && <div className="form-alert" role="alert">{error}</div>}

        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="email">อีเมลผู้ใช้งาน</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            placeholder="name@hospital.org"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <div className="password-label-row">
            <label htmlFor="password">รหัสผ่าน</label>
          </div>
          <div className="password-field">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="กรอกรหัสผ่านของคุณ"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <button
              type="button"
              className="password-toggle"
              aria-label={showPassword ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"}
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>

          <button className="login-submit" type="submit" disabled={isLoading}>
            <span>{isLoading ? "กำลังตรวจสอบ..." : "เข้าสู่ระบบ"}</span>
            <ArrowRight size={18} />
          </button>
        </form>

        <div className="login-security">
          <ShieldCheck size={17} />
          <span>สำหรับเจ้าหน้าที่ไอทีที่ได้รับอนุญาตเท่านั้น</span>
        </div>
        <div className="login-footnote">
          ระบบนี้วิเคราะห์เฉพาะข้อมูลเมตาและสถิติการใช้งานเครือข่าย
        </div>
      </section>
      <footer className="login-footer">ศูนย์เฝ้าระวังเครือข่ายโรงพยาบาล <span>·</span> ระบบภายใน</footer>
    </main>
  );
}
