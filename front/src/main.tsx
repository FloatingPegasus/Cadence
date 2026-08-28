import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/source-sans-3/latin-400.css";
import "@fontsource/source-sans-3/latin-500.css";
import "@fontsource/source-serif-4/latin-500.css";
import "@fontsource/source-serif-4/latin-600.css";
import App from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import "./styles/base.css";

ReactDOM.createRoot(document.getElementById("app")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>
);