'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, Lock, Mail, ArrowRight, AlertCircle, Info } from 'lucide-react';
import { authService } from '../services/authService';
import { ForgotPasswordModal } from './ForgotPasswordModal';

export const LoginForm: React.FC = () => {
  const router = useRouter();
  const [email, setEmail] = useState('worker@buildora.com');
  const [password, setPassword] = useState('password123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showForgotModal, setShowForgotModal] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await authService.login(email, password);
      localStorage.setItem('buildora_token', data.access_token);
      localStorage.setItem(
        'buildora_user',
        JSON.stringify({
          id: data.user_id,
          full_name: data.full_name,
          email: email,
          role: data.role,
        })
      );

      // Role-Based Redirection
      if (data.role === 'ADMIN') {
        router.push('/dashboard/admin');
      } else if (data.role === 'HR_MANAGER') {
        router.push('/dashboard/hr');
      } else {
        router.push('/dashboard/user');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid login credentials.');
    } finally {
      setLoading(false);
    }
  };

  const setPresetCredentials = (presetRole: string) => {
    if (presetRole === 'WORKER') {
      setEmail('worker@buildora.com');
      setPassword('password123');
    } else if (presetRole === 'ADMIN') {
      setEmail('admin@buildora.com');
      setPassword('admin123');
    } else if (presetRole === 'HR') {
      setEmail('hr@buildora.com');
      setPassword('hr123');
    }
  };

  return (
    <div className="w-full max-w-md bg-white rounded-2xl p-8 shadow-xl border border-stone-200">
      {/* Header Logo */}
      <div className="flex flex-col items-center mb-6">
        <div className="bg-[#C28E64] p-3 rounded-2xl text-white mb-3 shadow-md">
          <Building2 className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-bold text-stone-900 tracking-tight">BUILDORA</h2>
        <p className="text-xs text-stone-500 font-medium">Enterprise Construction Management</p>
      </div>

      {/* Preset Quick Fill Demo Buttons */}
      <div className="mb-6 bg-amber-50/70 p-3 rounded-xl border border-amber-200">
        <div className="flex items-center space-x-1.5 text-xs font-bold text-amber-900 mb-2">
          <Info className="w-4 h-4 text-amber-700" />
          <span>Quick Demo One-Click Login:</span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => setPresetCredentials('WORKER')}
            className="px-2 py-1.5 bg-white border border-amber-300 text-amber-900 text-xs rounded-lg hover:bg-amber-100 font-medium transition text-center"
          >
            Worker
          </button>
          <button
            type="button"
            onClick={() => setPresetCredentials('ADMIN')}
            className="px-2 py-1.5 bg-white border border-purple-300 text-purple-900 text-xs rounded-lg hover:bg-purple-100 font-medium transition text-center"
          >
            Admin
          </button>
          <button
            type="button"
            onClick={() => setPresetCredentials('HR')}
            className="px-2 py-1.5 bg-white border border-blue-300 text-blue-900 text-xs rounded-lg hover:bg-blue-100 font-medium transition text-center"
          >
            HR Manager
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-xs p-3 rounded-xl flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-stone-700 mb-1">Email Address</label>
          <div className="relative">
            <Mail className="w-5 h-5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#C28E64] bg-stone-50/50"
              placeholder="name@buildora.com"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-stone-700 mb-1">Password</label>
          <div className="relative">
            <Lock className="w-5 h-5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#C28E64] bg-stone-50/50"
              placeholder="••••••••"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setShowForgotModal(true)}
            className="text-xs text-[#C28E64] hover:underline font-medium"
          >
            Forgot password?
          </button>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-[#C28E64] hover:bg-[#A8754F] text-white py-3 rounded-xl font-bold text-sm transition shadow-md flex items-center justify-center space-x-2"
        >
          <span>{loading ? 'Authenticating...' : 'Sign In to Buildora'}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      <ForgotPasswordModal isOpen={showForgotModal} onClose={() => setShowForgotModal(false)} />
    </div>
  );
};
