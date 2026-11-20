import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { api } from "../services/api.js";

export function useDashboardData() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(async (signal) => {
    setIsLoading(true);
    setError("");
    try {
      const [overviewResponse, trafficResponse, statusResponse] = await Promise.all([
        api.get("/dashboard/overview", { signal }),
        api.get("/dashboard/traffic?hours=24", { signal }),
        api.get("/dashboard/device-status", { signal }),
      ]);
      setData({
        overview: overviewResponse.data,
        traffic: trafficResponse.data,
        deviceStatus: statusResponse.data,
      });
    } catch (requestError) {
      if (!axios.isCancel(requestError)) {
        setError(
          requestError?.response
            ? "โหลดข้อมูลไม่สำเร็จ กรุณาลองใหม่อีกครั้ง"
            : "ไม่สามารถเชื่อมต่อ API ได้ ตรวจสอบสถานะเซิร์ฟเวอร์",
        );
      }
    } finally {
      if (!signal.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, refreshKey]);

  return { data, isLoading, error, reload: () => setRefreshKey((key) => key + 1) };
}
