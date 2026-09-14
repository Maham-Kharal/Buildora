'use client';

import React from 'react';
import { Receipt } from '@/core/types';
import { FileText, Calendar, DollarSign, Tag, CheckCircle2, Clock, AlertTriangle, Eye } from 'lucide-react';

interface SubmittedReceiptsListProps {
  receipts: Receipt[];
}

export const SubmittedReceiptsList: React.FC<SubmittedReceiptsListProps> = ({ receipts }) => {
  if (receipts.length === 0) {
    return (
      <div className="bg-white rounded-2xl p-8 text-center border border-stone-200">
        <FileText className="w-12 h-12 text-stone-300 mx-auto mb-3" />
        <h4 className="text-base font-bold text-stone-700">No Expenses Submitted Yet</h4>
        <p className="text-xs text-stone-400 mt-1">
          Upload your physical receipt images above to track expense submissions.
        </p>
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>APPROVED</span>
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>REJECTED</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-700">
            <Clock className="w-3.5 h-3.5" />
            <span>PENDING</span>
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-stone-900">Your Submitted Expense History</h3>
          <p className="text-xs text-stone-500">Track status of submitted field receipts ($USD)</p>
        </div>
        <span className="bg-stone-100 text-stone-700 text-xs font-bold px-3 py-1 rounded-full border border-stone-200">
          {receipts.length} Submissions
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-stone-200 text-[11px] font-bold text-stone-400 uppercase tracking-wider">
              <th className="py-3 px-3">Date</th>
              <th className="py-3 px-3">Vendor</th>
              <th className="py-3 px-3">Category</th>
              <th className="py-3 px-3">Amount ($USD)</th>
              <th className="py-3 px-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100 text-sm">
            {receipts.map((r) => (
              <tr key={r.id} className="hover:bg-stone-50/80 transition">
                <td className="py-3.5 px-3 font-medium text-stone-600">
                  {r.purchase_date || r.created_at?.split('T')[0]}
                </td>
                <td className="py-3.5 px-3 font-bold text-stone-900">{r.vendor_name}</td>
                <td className="py-3.5 px-3 text-stone-500 text-xs">{r.category || 'Materials'}</td>
                <td className="py-3.5 px-3 font-mono font-bold text-stone-900">
                  ${r.total_amount.toFixed(2)}
                </td>
                <td className="py-3.5 px-3">{getStatusBadge(r.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
