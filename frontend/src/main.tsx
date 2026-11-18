import axios from "axios";
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

const applyAuthToken = () => {
  const token = localStorage.getItem("authToken");
  if (!token) {
    delete axios.defaults.headers.common.Authorization;
    return;
  }
  axios.defaults.headers.common.Authorization = `Bearer ${token}`;
};

applyAuthToken();

axios.interceptors.request.use((config) => {
  const token = localStorage.getItem("authToken");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("authToken");
      localStorage.removeItem("isAuthenticated");
      localStorage.removeItem("usuario");

      if (!window.location.pathname.toLowerCase().includes("/login")) {
        window.location.replace("/pesquisaAcionamento/login");
      }
    }

    return Promise.reject(error);
  },
);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
