import DashboardPage from "./components/DashboardPage";
import LoginPage from "./components/LoginPage";
import VerifyPage from "./components/VerifyPage";
import { useAuth } from "./contexts/AuthContext";

function App() {
  const { token } = useAuth();

  const isVerifyPage = window.location.pathname === "/verify" || !!new URLSearchParams(window.location.search).get("token");

  if (isVerifyPage) {
    return <VerifyPage />;
  }

  if (!token) {
    return <LoginPage />;
  }

  return <DashboardPage />;
}

export default App;
