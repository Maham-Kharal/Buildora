'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const userStr = localStorage.getItem('buildora_user');
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        if (user.role === 'ADMIN') {
          router.push('/dashboard/admin');
        } else if (user.role === 'HR_MANAGER') {
          router.push('/dashboard/hr');
        } else {
          router.push('/dashboard/user');
        }
        return;
      } catch (e) {
        // Fallback to login
      }
    }
    router.push('/login');
  }, [router]);

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex items-center justify-center">
      <div className="animate-pulse text-[#C28E64] font-bold text-lg">
        Loading Buildora System...
      </div>
    </div>
  );
}
