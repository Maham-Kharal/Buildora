'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, Loader2 } from 'lucide-react';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    try {
      const userStr = localStorage.getItem('buildora_user');
      if (userStr) {
        const user = JSON.parse(userStr);
        let target = '/dashboard/user';
        if (user.role === 'ADMIN') target = '/dashboard/admin';
        else if (user.role === 'HR_MANAGER') target = '/dashboard/hr';
        
        router.push(target);
        setTimeout(() => { window.location.href = target; }, 300);
        return;
      }
    } catch (e) {
      console.error(e);
    }
    
    router.push('/login');
    setTimeout(() => { window.location.href = '/login'; }, 300);
  }, [router]);

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col items-center justify-center space-y-4">
      <div className="bg-[#C28E64] p-3 rounded-2xl text-white shadow-lg">
        <Building2 className="w-8 h-8" />
      </div>
      <div className="flex items-center space-x-2 text-[#C28E64] font-bold text-base">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span>Loading Buildora Enterprise System...</span>
      </div>
    </div>
  );
}
