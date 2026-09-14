'use client';

import React from 'react';
import { ExpenseReportSummary } from '@/core/types';
import { DollarSign, FileCheck, AlertTriangle, Layers, TrendingUp } from 'lucide-react';

interface ExpenseReportGeneratorProps {
  summary: ExpenseReportSummary | null;
}

export const ExpenseReportGenerator: React.FC<ExpenseReportGeneratorProps> = ({ summary }) => {
  if (!summary) return null;

  return (
    <div className="space-y-6">
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center space-x-4">
          <div className="bg-emerald-100 p-3 rounded-2xl text-emerald-700">
            <DollarSign className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 font-bold uppercase tracking-wider block">Total USD Spend</span>
            <span className="text-2xl font-extrabold text-stone-900">${summary.total_spend_usd.toFixed(2)}</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center space-x-4">
          <div className="bg-blue-100 p-3 rounded-2xl text-blue-700">
            <FileCheck className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 font-bold uppercase tracking-wider block">Total Receipts</span>
            <span className="text-2xl font-extrabold text-stone-900">{summary.total_receipts}</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center space-x-4">
          <div className="bg-amber-100 p-3 rounded-2xl text-amber-700">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 font-bold uppercase tracking-wider block">Tavily Anomalies</span>
            <span className="text-2xl font-extrabold text-amber-900">{summary.flagged_anomalies_count}</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center space-x-4">
          <div className="bg-purple-100 p-3 rounded-2xl text-purple-700">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-stone-400 font-bold uppercase tracking-wider block">Approved / Pending</span>
            <span className="text-2xl font-extrabold text-stone-900">
              {summary.approved_count} / {summary.pending_approval_count}
            </span>
          </div>
        </div>
      </div>

      {/* Category Breakdown Table */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <h4 className="text-base font-bold text-stone-900 mb-4 flex items-center space-x-2">
          <Layers className="w-5 h-5 text-[#C28E64]" />
          <span>Expense Distribution by Category ($USD)</span>
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {summary.by_category.map((cat, idx) => (
            <div key={idx} className="bg-stone-50 p-4 rounded-xl border border-stone-200 flex justify-between items-center">
              <div>
                <span className="font-bold text-stone-800 block text-sm">{cat.category}</span>
                <span className="text-xs text-stone-400">{cat.receipt_count} Receipts</span>
              </div>
              <span className="font-mono font-extrabold text-stone-900 text-lg">
                ${cat.total_amount.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
