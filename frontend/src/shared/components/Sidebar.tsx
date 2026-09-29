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
  isCollapsed?: boolean;
  hideLogoutInSidebar?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  role, 
  activeTab, 
  setActiveTab,
  isCollapsed = false,
  hideLogoutInSidebar = false
}) => {
  const handleLogout = () => {
    localStorage.removeItem('buildora_token');
    localStorage.removeItem('buildora_user');
    window.location.href = '/login';
  };

  const adminNavs = [
    { id: 'projects', label: 'Project Management', icon: Building2 },
    { id: 'receipts', label: 'Receipt Monitoring', icon: FileText },
    { id: 'audit', label: 'Audit Logs', icon: ShieldCheck },
  ];

  const hrNavs = [
    { id: 'users', label: 'Employee Accounts', icon: Users },
    { id: 'leaves', label: 'Leave Approvals', icon: CalendarDays },
    { id: 'policies', label: 'Company Policy KB', icon: BookOpen },
  ];

  const navItems = role === 'ADMIN' ? adminNavs : hrNavs;

  return (
    <aside className={`${isCollapsed ? 'w-20' : 'w-64'} bg-[#1E1E1E] text-white min-h-screen flex flex-col p-4 justify-between transition-all duration-300 shrink-0`}>
      <div>
        {/* Brand Logo */}
        <div className={`flex items-center space-x-3 mb-8 px-2 ${isCollapsed ? 'justify-center space-x-0' : ''}`}>
          <div className="bg-[#C28E64] p-2 rounded-xl text-white shrink-0">
            <Building2 className="w-6 h-6" />
          </div>
          {!isCollapsed && (
            <div>
              <h1 className="font-bold text-xl tracking-wide">BUILDORA</h1>
              <p className="text-xs text-stone-400">Enterprise Operations</p>
            </div>
          )}
        </div>

        {/* Console Indicator */}
        {!isCollapsed && (
          <div className="mb-6 px-2">
            <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
              {role === 'ADMIN' ? 'Admin Operations Console' : 'HR Management Console'}
            </span>
          </div>
        )}

        {/* Navigation Items */}
        <nav className="space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab && setActiveTab(item.id)}
                title={item.label}
                className={`w-full flex items-center ${isCollapsed ? 'justify-center px-0 py-3' : 'space-x-3 px-4 py-3'} rounded-xl transition text-sm font-medium ${
                  isActive
                    ? 'bg-[#C28E64] text-white shadow-md'
                    : 'text-stone-300 hover:bg-stone-800 hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5 shrink-0" />
                {!isCollapsed && <span>{item.label}</span>}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Optional Sidebar Logout */}
      {!hideLogoutInSidebar && (
        <div className="pt-6 border-t border-stone-800">
          <button
            onClick={handleLogout}
            title="Sign Out"
            className={`w-full flex items-center ${isCollapsed ? 'justify-center px-0 py-3' : 'space-x-3 px-4 py-3'} rounded-xl text-red-400 hover:bg-red-500/10 transition text-sm font-medium`}
          >
            <LogOut className="w-5 h-5 shrink-0" />
            {!isCollapsed && <span>Sign Out</span>}
          </button>
        </div>
      )}
    </aside>
  );
};
