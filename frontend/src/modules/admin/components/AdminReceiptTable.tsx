'use client';

import React from 'react';
import { Receipt } from '@/core/types';
import { adminService } from '../services/adminService';
import { AlertTriangle, CheckCircle, XCircle, FileText, User, DollarSign, Calendar } from 'lucide-react';

interface AdminReceiptTableProps {
  receipts: Receipt[];
  onRefresh: () => void;
}

export const AdminReceiptTable: React.FC<AdminReceiptTableProps> = ({ receipts, onRefresh }) => {
  const handleStatusUpdate = async (id: number, newStatus: 'APPROVED' | 'REJECTED') => {
    try {
      await adminService.updateReceiptStatus(id, newStatus);
      onRefresh();
    } catch (err) {
      alert('Failed to update receipt status.');
    }
  };

  return (
    <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-bold text-stone-900">Enterprise Receipt Monitoring & Verification</h3>
          <p className="text-xs text-stone-500">
            Real-time Tavily price anomaly detection (>15% market benchmark warning)
          </p>
        </div>
        <span className="bg-[#C28E64]/10 text-[#C28E64] font-bold text-xs px-3.5 py-1.5 rounded-full border border-[#C28E64]/20">
          {receipts.length} Total Receipts
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-stone-200 text-[11px] font-bold text-stone-400 uppercase tracking-wider">
              <th className="py-3 px-3">ID / User</th>
              <th className="py-3 px-3">Vendor</th>
              <th className="py-3 px-3">Category</th>
              <th className="py-3 px-3">Total ($USD)</th>
              <th className="py-3 px-3">Tavily Anomaly Check</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100 text-sm">
            {receipts.map((r) => (
              <tr key={r.id} className="hover:bg-stone-50/80 transition">
                <td className="py-4 px-3">
                  <div className="font-bold text-stone-900">#{r.id}</div>
                  <div className="text-xs text-stone-500 flex items-center space-x-1">
                    <User className="w-3 h-3 text-stone-400" />
                    <span>{r.user_name || `User #${r.user_id}`}</span>
                  </div>
                </td>
                <td className="py-4 px-3 font-semibold text-stone-800">{r.vendor_name}</td>
                <td className="py-4 px-3 text-xs text-stone-500">{r.category || 'Materials'}</td>
                <td className="py-4 px-3 font-mono font-bold text-stone-900">
                  ${r.total_amount.toFixed(2)}
                </td>
                <td className="py-4 px-3">
                  {r.flagged_anomaly ? (
                    <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300 animate-pulse">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
                      <span>&gt;15% Price Anomaly</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                      <span>Normal Market Rate</span>
                    </span>
                  )}
                </td>
                <td className="py-4 px-3">
                  <span
                    className={`inline-block text-xs font-bold px-2.5 py-1 rounded-full ${
                      r.status === 'APPROVED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : r.status === 'REJECTED'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {r.status}
                  </span>
                </td>
                <td className="py-4 px-3 text-right">
                  {r.status === 'PENDING' && (
                    <div className="flex items-center justify-end space-x-2">
                      <button
                        onClick={() => handleStatusUpdate(r.id, 'APPROVED')}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs rounded-xl font-bold transition shadow-sm"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleStatusUpdate(r.id, 'REJECTED')}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs rounded-xl font-bold transition shadow-sm"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
