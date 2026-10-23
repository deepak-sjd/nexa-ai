import App from "../App.jsx";
import AuthPage from "./AuthPage";
import { useAuth } from "../context/useAuth";

export default function AuthGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="auth-loading" role="status">
        <div className="auth-loading-dot" />
        <p>Connecting to NEXA AI...</p>
        <span>The first visit can take up to a minute.</span>
      </div>
    );
  }

  return user ? <App /> : <AuthPage />;
}
