'use client';

import React, { useState } from 'react';
import { Modal } from '@/shared/components/Modal';
import { UserProfile } from '@/core/types';
import { hrService } from '../services/hrService';
import { KeyRound, CheckCircle } from 'lucide-react';

interface PasswordResetModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile | null;
  onSuccess: () => void;
}

export const PasswordResetModal: React.FC<PasswordResetModalProps> = ({
  isOpen,
  onClose,
  user,
  onSuccess,
}) => {
  const [newPassword, setNewPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  if (!user) return null;

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccessMsg('');

    try {
      await hrService.resetPassword(user.id, newPassword);
      setSuccessMsg(`Password successfully reset for ${user.full_name}`);
      setNewPassword('');
      setTimeout(() => {
        setSuccessMsg('');
        onClose();
        onSuccess();
      }, 1500);
    } catch (err) {
      alert('Error resetting user password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Reset Password for ${user.full_name}`}>
      <form onSubmit={handleReset} className="space-y-4">
        {successMsg && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs p-3 rounded-xl flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-bold text-stone-700 mb-1">New Password</label>
          <input
            type="password"
            required
            minLength={6}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Enter new passcode..."
            className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
          />
        </div>

        <div className="flex justify-end space-x-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 text-xs font-bold rounded-xl"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading || !newPassword}
            className="px-5 py-2 bg-[#C28E64] hover:bg-[#A8754F] text-white text-xs font-bold rounded-xl shadow"
          >
            {loading ? 'Resetting...' : 'Confirm Reset'}
          </button>
        </div>
      </form>
    </Modal>
  );
};
