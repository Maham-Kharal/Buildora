'use client';

import React from 'react';
import { Modal } from '@/shared/components/Modal';
import { ShieldAlert, Mail } from 'lucide-react';

interface ForgotPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ForgotPasswordModal: React.FC<ForgotPasswordModalProps> = ({ isOpen, onClose }) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Password Reset Request">
      <div className="text-center space-y-4">
        <div className="bg-amber-100 p-3 rounded-full w-12 h-12 flex items-center justify-center mx-auto text-amber-700">
          <ShieldAlert className="w-6 h-6" />
        </div>
        
        <div className="text-stone-600 text-sm space-y-2">
          <p className="font-semibold text-stone-900">Buildora Enterprise Security Policy</p>
          <p>
            For organizational security, password resets are handled directly by your designated **HR Manager**.
          </p>
          <p className="text-xs bg-stone-100 p-3 rounded-xl border border-stone-200 text-stone-700">
            Please submit a request to <span className="font-bold">hr@buildora.com</span> or contact your HR department to issue a temporary passcode.
          </p>
        </div>

        <button
          onClick={onClose}
          className="w-full bg-[#C28E64] text-white font-bold py-2.5 rounded-xl hover:bg-[#A8754F] transition text-sm shadow"
        >
          Understood
        </button>
      </div>
    </Modal>
  );
};
