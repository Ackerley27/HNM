import axios from "axios";

let accessToken = null;

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 12000,
  headers: { "Content-Type": "application/json" },
});

export function setAccessToken(token) {
  accessToken = token;
}

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.endsWith("/auth/login")
    ) {
      window.dispatchEvent(new Event("auth:expired"));
    }
    return Promise.reject(error);
  },
);
