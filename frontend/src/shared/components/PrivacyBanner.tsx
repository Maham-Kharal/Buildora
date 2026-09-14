'use client';

import React from 'react';
import { ShieldCheck } from 'lucide-react';

export const PrivacyBanner: React.FC = () => {
  return (
    <div className="inline-flex items-center space-x-2 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs px-3.5 py-1.5 rounded-full font-medium shadow-sm">
      <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
      <span>US Data Isolation • Zero-Cost Local Storage ($0 USD)</span>
    </div>
  );
};
