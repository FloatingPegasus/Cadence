import DashboardPage from "./components/DashboardPage";
import LoginPage from "./components/LoginPage";
import VerifyPage from "./components/VerifyPage";
import { useAuth } from "./contexts/AuthContext";

function App() {
  const { user, isLoading } = useAuth();

  const isVerifyPage = window.location.pathname === "/verify" || !!new URLSearchParams(window.location.search).get("token");

  if (isVerifyPage) {
    return <VerifyPage />;
  }

  if (isLoading) {
    return (
      <div className="max-w-sm mx-auto px-6 py-20 text-center text-sm text-neutral-500">
        Loading your session...
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return <DashboardPage />;
}

export default App;
