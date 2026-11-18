import { BrowserRouter, Routes, Route } from "react-router-dom";
import Login from "./login";
import NotFound from "./NotFound";
import { Navigate } from "react-router-dom";
import Home from "./Home";

export function ProtectedRoute({ children }) {
  const isAuthenticated = localStorage.getItem("isAuthenticated") === "true";
  const token = localStorage.getItem("authToken");

  if (!isAuthenticated || !token) {
    return <Navigate to="/pesquisaacionamento/login" replace />;
  }

  return children;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="pesquisaAcionamento/login"
          element={<Login />}
        />
        <Route
          path="pesquisaAcionamento/home"
          element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }
        />

        {/* rota 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
