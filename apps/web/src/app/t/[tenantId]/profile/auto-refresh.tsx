"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

// While the profile is updating in the background, refresh the server data every few seconds.
export function AutoRefresh({ seconds }: { seconds: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(id);
  }, [router, seconds]);
  return null;
}
