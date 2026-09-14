'use client';

import React from 'react';
import { LeaveRequest } from '@/core/types';
import { hrService } from '../services/hrService';
import { CalendarDays, CheckCircle, XCircle, Sparkles, Clock } from 'lucide-react';

interface LeaveApprovalsListProps {
  leaves: LeaveRequest[];
  onRefresh: () => void;
}

export const LeaveApprovalsList: React.FC<LeaveApprovalsListProps> = ({ leaves, onRefresh }) => {
  const handleUpdateStatus = async (id: number, status: 'APPROVED' | 'REJECTED') => {
    try {
      await hrService.updateLeaveStatus(id, status);
      onRefresh();
    } catch (err) {
      alert('Failed to update leave request status.');
    }
  };

  return (
    <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-stone-900">Employee Leave Request Queue</h3>
          <p className="text-xs text-stone-500">
            Automated preliminary clearance applied for leave requests under 3 days
          </p>
        </div>
        <span className="bg-stone-100 text-stone-700 font-bold text-xs px-3 py-1 rounded-full border border-stone-200">
          {leaves.length} Total Requests
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-stone-200 text-[11px] font-bold text-stone-400 uppercase tracking-wider">
              <th className="py-3 px-3">Employee</th>
              <th className="py-3 px-3">Dates</th>
              <th className="py-3 px-3">Duration</th>
              <th className="py-3 px-3">Reason</th>
              <th className="py-3 px-3">Auto Clearance</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100 text-sm">
            {leaves.map((l) => (
              <tr key={l.id} className="hover:bg-stone-50 transition">
                <td className="py-3.5 px-3 font-bold text-stone-900">
                  {l.user_name || `User #${l.user_id}`}
                </td>
                <td className="py-3.5 px-3 text-xs text-stone-600">
                  {l.start_date} to {l.end_date}
                </td>
                <td className="py-3.5 px-3 font-semibold text-stone-800">{l.days} Days</td>
                <td className="py-3.5 px-3 text-xs text-stone-500 max-w-xs truncate">{l.reason}</td>
                <td className="py-3.5 px-3">
                  {l.auto_approved ? (
                    <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                      <Sparkles className="w-3 h-3 text-emerald-600" />
                      <span>Auto-Approved (&lt;3 Days)</span>
                    </span>
                  ) : (
                    <span className="text-xs text-stone-400 font-medium">Standard HR Review</span>
                  )}
                </td>
                <td className="py-3.5 px-3">
                  <span
                    className={`inline-block text-xs font-bold px-2.5 py-0.5 rounded-full ${
                      l.status === 'APPROVED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : l.status === 'REJECTED'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {l.status}
                  </span>
                </td>
                <td className="py-3.5 px-3 text-right">
                  {l.status === 'PENDING' && (
                    <div className="flex items-center justify-end space-x-2">
                      <button
                        onClick={() => handleUpdateStatus(l.id, 'APPROVED')}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-sm"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleUpdateStatus(l.id, 'REJECTED')}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-xl shadow-sm"
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
