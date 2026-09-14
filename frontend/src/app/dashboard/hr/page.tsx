'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/shared/components/Sidebar';
import { Header } from '@/shared/components/Header';
import { UserManagementTable } from '@/modules/hr/components/UserManagementTable';
import { LeaveApprovalsList } from '@/modules/hr/components/LeaveApprovalsList';
import { PolicyManager } from '@/modules/hr/components/PolicyManager';
import { hrService } from '@/modules/hr/services/hrService';
import { UserProfile, LeaveRequest, CompanyPolicy } from '@/core/types';

export default function HRDashboard() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [leaves, setLeaves] = useState<LeaveRequest[]>([]);
  const [policies, setPolicies] = useState<CompanyPolicy[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userStr = localStorage.getItem('buildora_user');
    if (!userStr) {
      router.push('/login');
      return;
    }
    const parsedUser = JSON.parse(userStr);
    if (parsedUser.role !== 'HR_MANAGER' && parsedUser.role !== 'ADMIN') {
      router.push('/login');
      return;
    }
    setUser(parsedUser);

    loadHRData();
  }, [router]);

  const loadHRData = async () => {
    setLoading(true);
    try {
      const [uData, lData, pData] = await Promise.all([
        hrService.getUsers(),
        hrService.getLeaves(),
        hrService.getPolicies(),
      ]);
      setUsers(uData);
      setLeaves(lData);
      setPolicies(pData);
    } catch (err) {
      console.error('Failed to load HR dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex">
      {/* Left Sidebar Layout */}
      <Sidebar role="HR_MANAGER" activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Content View */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header user={user} title="HR Management Console" />

        <main className="flex-1 p-6 md:p-8 space-y-6 overflow-y-auto">
          {loading ? (
            <div className="text-center py-12 text-stone-400 font-semibold text-sm">
              Loading HR records...
            </div>
          ) : (
            <>
              {activeTab === 'users' && (
                <UserManagementTable users={users} onRefresh={loadHRData} />
              )}

              {activeTab === 'leaves' && (
                <LeaveApprovalsList leaves={leaves} onRefresh={loadHRData} />
              )}

              {activeTab === 'policies' && (
                <PolicyManager policies={policies} onRefresh={loadHRData} />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
