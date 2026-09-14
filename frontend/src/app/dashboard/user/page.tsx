'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Header } from '@/shared/components/Header';
import { ReceiptUploader } from '@/modules/user/components/ReceiptUploader';
import { SubmittedReceiptsList } from '@/modules/user/components/SubmittedReceiptsList';
import { AiAssistantDrawer } from '@/modules/user/components/AiAssistantDrawer';
import { userService } from '@/modules/user/services/userService';
import { Receipt } from '@/core/types';

export default function WorkerDashboard() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userStr = localStorage.getItem('buildora_user');
    if (!userStr) {
      router.push('/login');
      return;
    }
    const parsedUser = JSON.parse(userStr);
    setUser(parsedUser);

    fetchReceipts();
  }, [router]);

  const fetchReceipts = async () => {
    try {
      const data = await userService.getMyReceipts();
      setReceipts(data);
    } catch (err) {
      console.error('Failed to load user receipts:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReceiptAdded = (newReceipt: Receipt) => {
    setReceipts((prev) => [newReceipt, ...prev]);
  };

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col">
      {/* Top Header WITHOUT Left Sidebar - matching user layout mockup */}
      <Header user={user} showLogoutInHeader={true} />

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 md:p-8 space-y-8">
        {/* Receipt Upload Box */}
        <section>
          <ReceiptUploader onSuccess={handleReceiptAdded} />
        </section>

        {/* Submitted Receipts Table */}
        <section>
          {loading ? (
            <div className="text-center py-8 text-stone-400 text-sm font-semibold">
              Loading expense history...
            </div>
          ) : (
            <SubmittedReceiptsList receipts={receipts} />
          )}
        </section>
      </main>

      {/* Floating Bottom-Right AI HR Assistant Drawer */}
      <AiAssistantDrawer />
    </div>
  );
}
