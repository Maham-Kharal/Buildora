'use client';

import React from 'react';
import { User, LogOut, ShieldCheck, Building2 } from 'lucide-react';
import { PrivacyBanner } from './PrivacyBanner';

interface HeaderProps {
  user?: {
    full_name: string;
    email: string;
    role: string;
  } | null;
  title?: string;
  showLogoutInHeader?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ user, title, showLogoutInHeader = false }) => {
  const handleLogout = () => {
    localStorage.removeItem('buildora_token');
    localStorage.removeItem('buildora_user');
    window.location.href = '/login';
  };

  const getRoleBadgeColor = (role?: string) => {
    switch (role) {
      case 'ADMIN':
        return 'bg-purple-100 text-purple-700 border-purple-200';
      case 'HR_MANAGER':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      default:
        return 'bg-amber-100 text-amber-800 border-amber-200';
    }
  };

  return (
    <header className="bg-white border-b border-stone-200 px-8 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex items-center space-x-4">
        {/* Mobile / Worker Logo */}
        {!title && (
          <div className="bg-[#C28E64] p-2.5 rounded-2xl text-white flex items-center justify-center">
            <Building2 className="w-6 h-6" />
          </div>
        )}
        <div>
          <h2 className="text-xl font-bold text-stone-900 tracking-tight">
            {title || `Welcome back, ${user?.full_name || 'Team Member'}`}
          </h2>
          <p className="text-xs text-stone-500 font-medium">
            Buildora US Enterprise Construction Platform ($USD)
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Privacy Pill */}
        <PrivacyBanner />

        {/* User Info */}
        {user && (
          <div className="flex items-center space-x-3 bg-stone-50 border border-stone-200 px-3.5 py-1.5 rounded-full">
            <div className="bg-[#C28E64]/20 p-1.5 rounded-full text-[#C28E64]">
              <User className="w-4 h-4" />
            </div>
            <div className="text-xs">
              <span className="font-semibold text-stone-800 block">{user.full_name}</span>
              <span className={`inline-block text-[10px] px-2 py-0.5 rounded-full font-bold uppercase border ${getRoleBadgeColor(user.role)}`}>
                {user.role}
              </span>
            </div>
          </div>
        )}

        {/* Worker Top Logout Button */}
        {showLogoutInHeader && (
          <button
            onClick={handleLogout}
            title="Sign Out"
            className="p-2 text-stone-500 hover:text-red-600 hover:bg-red-50 rounded-xl transition"
          >
            <LogOut className="w-5 h-5" />
          </button>
        )}
      </div>
    </header>
  );
};
