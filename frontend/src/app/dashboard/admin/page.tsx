'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/shared/components/Sidebar';
import { Header } from '@/shared/components/Header';
import { AdminReceiptTable } from '@/modules/admin/components/AdminReceiptTable';
import { ExpenseReportGenerator } from '@/modules/admin/components/ExpenseReportGenerator';
import { SteelEstimatorChat } from '@/modules/admin/components/SteelEstimatorChat';
import { ProjectManagement } from '@/modules/admin/components/ProjectManagement';
import { AiAssistantDrawer } from '@/modules/user/components/AiAssistantDrawer';
import { adminService } from '@/modules/admin/services/adminService';
import { Receipt, ExpenseReportSummary, AuditLog } from '@/core/types';
import { ShieldCheck, Clock, User, Activity } from 'lucide-react';

export default function AdminDashboard() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('projects');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [summary, setSummary] = useState<ExpenseReportSummary | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let userToUse = null;
    const userStr = localStorage.getItem('buildora_user');
    
    if (userStr) {
      try {
        userToUse = JSON.parse(userStr);
      } catch (e) {
        console.error(e);
      }
    }

    if (!userToUse) {
      userToUse = {
        id: 2,
        email: 'admin@buildora.com',
        full_name: 'Sarah Admin',
        role: 'ADMIN',
      };
      localStorage.setItem('buildora_user', JSON.stringify(userToUse));
    }

    setUser(userToUse);
    loadDashboardData();
  }, [router]);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [rData, sData, aData] = await Promise.all([
        adminService.getReceipts(),
        adminService.getExpenseSummary(),
        adminService.getAuditLogs(),
      ]);
      setReceipts(rData);
      setSummary(sData);
      setAuditLogs(aData);
    } catch (err) {
      console.error('Failed to load admin dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex">
      {/* Left Sidebar Layout */}
      <Sidebar 
        role="ADMIN" 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        isCollapsed={sidebarCollapsed}
        hideLogoutInSidebar={true}
      />

      {/* Main Content View */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header 
          user={user} 
          title="Admin Operations Console" 
          showLogoutInHeader={true}
          onToggleSidebar={() => setSidebarCollapsed((prev) => !prev)}
        />

        <main className="flex-1 p-6 md:p-8 space-y-6 overflow-y-auto">
          {loading ? (
            <div className="text-center py-12 text-stone-400 font-semibold text-sm">
              Loading admin data...
            </div>
          ) : (
            <>
              {activeTab === 'projects' && (
                <ProjectManagement />
              )}

              {activeTab === 'receipts' && (
                <AdminReceiptTable receipts={receipts} onRefresh={loadDashboardData} />
              )}

              {activeTab === 'reports' && (
                <ExpenseReportGenerator summary={summary} />
              )}

              {activeTab === 'steel' && (
                <SteelEstimatorChat />
              )}

              {activeTab === 'audit' && (
                <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
                  <div className="flex items-center space-x-3 mb-6">
                    <div className="bg-[#C28E64] p-2.5 rounded-xl text-white">
                      <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-stone-900">System Audit Trail</h3>
                      <p className="text-xs text-stone-500">Immutable security logs for admin review</p>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-stone-200 text-[11px] font-bold text-stone-400 uppercase tracking-wider">
                          <th className="py-3 px-3">Timestamp</th>
                          <th className="py-3 px-3">User</th>
                          <th className="py-3 px-3">Action</th>
                          <th className="py-3 px-3">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100 text-xs">
                        {auditLogs.map((log) => (
                          <tr key={log.id} className="hover:bg-stone-50 transition">
                            <td className="py-3 px-3 text-stone-400 font-mono">
                              {log.created_at?.replace('T', ' ')?.substring(0, 19)}
                            </td>
                            <td className="py-3 px-3 font-bold text-stone-800">{log.user_name}</td>
                            <td className="py-3 px-3 font-bold text-[#C28E64]">{log.action}</td>
                            <td className="py-3 px-3 text-stone-600">{log.details}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {/* Floating Buildora AI Assistant Drawer */}
      <AiAssistantDrawer />
    </div>
  );
}
