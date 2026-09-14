'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Building2, 
  FileText, 
  BarChart3, 
  Calculator, 
  ShieldCheck, 
  Users, 
  CalendarDays, 
  BookOpen, 
  LogOut 
} from 'lucide-react';

interface SidebarProps {
  role: 'ADMIN' | 'HR_MANAGER';
  activeTab?: string;
  setActiveTab?: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ role, activeTab, setActiveTab }) => {
  const handleLogout = () => {
    localStorage.removeItem('buildora_token');
    localStorage.removeItem('buildora_user');
    window.location.href = '/login';
  };

  const adminNavs = [
    { id: 'receipts', label: 'Receipt Monitoring', icon: FileText },
    { id: 'reports', label: 'Expense Reports', icon: BarChart3 },
    { id: 'steel', label: 'AI Steel Estimator', icon: Calculator },
    { id: 'audit', label: 'Audit Logs', icon: ShieldCheck },
  ];

  const hrNavs = [
    { id: 'users', label: 'Employee Accounts', icon: Users },
    { id: 'leaves', label: 'Leave Approvals', icon: CalendarDays },
    { id: 'policies', label: 'Company Policy KB', icon: BookOpen },
  ];

  const navItems = role === 'ADMIN' ? adminNavs : hrNavs;

  return (
    <aside className="w-64 bg-[#1E1E1E] text-white min-h-screen flex flex-col p-5 justify-between">
      <div>
        {/* Brand Logo */}
        <div className="flex items-center space-x-3 mb-8 px-2">
          <div className="bg-[#C28E64] p-2 rounded-xl text-white">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-bold text-xl tracking-wide">BUILDORA</h1>
            <p className="text-xs text-stone-400">Enterprise Operations</p>
          </div>
        </div>

        {/* Console Indicator */}
        <div className="mb-6 px-2">
          <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
            {role === 'ADMIN' ? 'Admin Operations Console' : 'HR Management Console'}
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab && setActiveTab(item.id)}
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition text-sm font-medium ${
                  isActive
                    ? 'bg-[#C28E64] text-white shadow-md'
                    : 'text-stone-300 hover:bg-stone-800 hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Logout */}
      <div className="pt-6 border-t border-stone-800">
        <button
          onClick={handleLogout}
          className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-red-400 hover:bg-red-500/10 transition text-sm font-medium"
        >
          <LogOut className="w-5 h-5" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
