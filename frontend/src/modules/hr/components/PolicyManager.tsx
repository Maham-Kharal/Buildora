'use client';

import React, { useState } from 'react';
import { CompanyPolicy } from '@/core/types';
import { hrService } from '../services/hrService';
import { BookOpen, Plus, Trash2, FileText } from 'lucide-react';

interface PolicyManagerProps {
  policies: CompanyPolicy[];
  onRefresh: () => void;
}

export const PolicyManager: React.FC<PolicyManagerProps> = ({ policies, onRefresh }) => {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('General');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await hrService.createPolicy({ title, category, content });
      setTitle('');
      setContent('');
      onRefresh();
    } catch (err) {
      alert('Failed to add policy document.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePolicy = async (id: number) => {
    if (!confirm('Are you sure you want to delete this policy document?')) return;
    try {
      await hrService.deletePolicy(id);
      onRefresh();
    } catch (err) {
      alert('Failed to delete policy document.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Create Policy Document Form */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center space-x-3 mb-4">
          <div className="bg-[#C28E64] p-2.5 rounded-xl text-white">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-stone-900">Add Company Policy Knowledge Base Document</h3>
            <p className="text-xs text-stone-500">
              Policy documents are automatically fed into the AI HR Assistant for employee guidance
            </p>
          </div>
        </div>

        <form onSubmit={handleCreatePolicy} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-stone-700 mb-1">Policy Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Paid Time Off (PTO) & Leave Entitlements"
                className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-stone-700 mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
              >
                <option value="General">General HR Policies</option>
                <option value="Leave & Benefits">Leave & Benefits</option>
                <option value="Safety & Site">Safety & Field Site Rules</option>
                <option value="Expenses">Reimbursement & Expenses</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Policy Content / Guidelines</label>
            <textarea
              required
              rows={3}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Detail company rules, entitlements, and procedures..."
              className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            ></textarea>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="bg-[#C28E64] hover:bg-[#A8754F] text-white px-6 py-2.5 rounded-xl font-bold text-sm shadow transition flex items-center space-x-2"
            >
              <Plus className="w-4 h-4" />
              <span>{loading ? 'Publishing Policy...' : 'Publish Policy Document'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Policy Documents List */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-stone-900">Active HR Policy Knowledge Base</h3>
            <p className="text-xs text-stone-500">
              Loaded policy documents index for Gemini AI HR Assistant
            </p>
          </div>
          <span className="bg-stone-100 text-stone-700 font-bold text-xs px-3 py-1 rounded-full border border-stone-200">
            {policies.length} Policies Active
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {policies.map((p) => (
            <div key={p.id} className="bg-stone-50 p-4 rounded-2xl border border-stone-200 flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold text-stone-900 text-sm flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-[#C28E64]" />
                    <span>{p.title}</span>
                  </h4>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-stone-200 text-stone-700 uppercase">
                    {p.category}
                  </span>
                </div>
                <p className="text-xs text-stone-600 leading-relaxed bg-white p-3 rounded-xl border border-stone-200">
                  {p.content}
                </p>
              </div>

              <div className="flex justify-end pt-3 mt-2 border-t border-stone-200">
                <button
                  onClick={() => handleDeletePolicy(p.id)}
                  className="text-red-500 hover:text-red-700 text-xs font-bold flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Delete Document</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
