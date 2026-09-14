'use client';

import React, { useState } from 'react';
import { UserProfile } from '@/core/types';
import { hrService } from '../services/hrService';
import { Users, UserPlus, KeyRound, Mail, UserCheck, Shield } from 'lucide-react';
import { PasswordResetModal } from './PasswordResetModal';

interface UserManagementTableProps {
  users: UserProfile[];
  onRefresh: () => void;
}

export const UserManagementTable: React.FC<UserManagementTableProps> = ({ users, onRefresh }) => {
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('WORKER');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [resetTargetUser, setResetTargetUser] = useState<UserProfile | null>(null);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await hrService.createUser({ email, full_name: fullName, role, password });
      setEmail('');
      setFullName('');
      setPassword('');
      onRefresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Error creating user account.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Onboarding Form */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center space-x-3 mb-4">
          <div className="bg-[#C28E64] p-2.5 rounded-xl text-white">
            <UserPlus className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-stone-900">Onboard New Employee Account</h3>
            <p className="text-xs text-stone-500">Assign temporary password & role credentials</p>
          </div>
        </div>

        <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Full Name</label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. John Doe"
              className="w-full px-3.5 py-2 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Company Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="johndoe@buildora.com"
              className="w-full px-3.5 py-2 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Assigned Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3.5 py-2 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            >
              <option value="WORKER">WORKER (Field Ops)</option>
              <option value="ADMIN">ADMIN (Operations & Takeoff)</option>
              <option value="HR_MANAGER">HR_MANAGER (Human Resources)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Temporary Passcode</label>
            <input
              type="text"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Passcode123!"
              className="w-full px-3.5 py-2 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            />
          </div>

          <div className="md:col-span-4 flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="bg-[#C28E64] hover:bg-[#A8754F] text-white px-6 py-2.5 rounded-xl font-bold text-sm shadow transition"
            >
              {loading ? 'Creating Account...' : 'Create Employee Account'}
            </button>
          </div>
        </form>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-stone-900">Registered Employee Directory</h3>
            <p className="text-xs text-stone-500">Active accounts and credential administration</p>
          </div>
          <span className="bg-stone-100 text-stone-700 font-bold text-xs px-3 py-1 rounded-full border border-stone-200">
            {users.length} Active Employees
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-stone-200 text-[11px] font-bold text-stone-400 uppercase tracking-wider">
                <th className="py-3 px-3">ID / User</th>
                <th className="py-3 px-3">Email</th>
                <th className="py-3 px-3">Role</th>
                <th className="py-3 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 text-sm">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-stone-50 transition">
                  <td className="py-3.5 px-3">
                    <div className="font-bold text-stone-900">{u.full_name}</div>
                    <div className="text-xs text-stone-400">ID #{u.id}</div>
                  </td>
                  <td className="py-3.5 px-3 text-stone-600 font-medium">{u.email}</td>
                  <td className="py-3.5 px-3">
                    <span
                      className={`inline-block text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                        u.role === 'ADMIN'
                          ? 'bg-purple-100 text-purple-800 border-purple-200'
                          : u.role === 'HR_MANAGER'
                          ? 'bg-blue-100 text-blue-800 border-blue-200'
                          : 'bg-amber-100 text-amber-800 border-amber-200'
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="py-3.5 px-3 text-right">
                    <button
                      onClick={() => setResetTargetUser(u)}
                      className="inline-flex items-center space-x-1 px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-700 text-xs font-bold rounded-xl transition border border-stone-200"
                    >
                      <KeyRound className="w-3.5 h-3.5 text-stone-500" />
                      <span>Reset Password</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <PasswordResetModal
        isOpen={!!resetTargetUser}
        onClose={() => setResetTargetUser(null)}
        user={resetTargetUser}
        onSuccess={onRefresh}
      />
    </div>
  );
};
