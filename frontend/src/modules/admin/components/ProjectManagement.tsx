'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { PlusCircle, CheckCircle, Loader2, AlertCircle, RefreshCw, Users } from 'lucide-react';
import { projectService } from '../services/projectService';
import { ActiveProject, AssignableUser } from '@/core/types';

const STRUCTURAL_OPTIONS = [
  'Reinforced Concrete Frame',
  'Structural Steel Framing',
  'Precast Concrete System',
  'Wood / Light-Frame',
  'Steel Moment Frame',
];

const EMPTY_FORM = {
  name: '',
  location: '',
  sqft: '' as unknown as number,
  floors: '' as unknown as number,
  structural_system: 'Reinforced Concrete Frame',
};

export const ProjectManagement: React.FC = () => {
  const [projects, setProjects] = useState<ActiveProject[]>([]);
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [selectedMemberIds, setSelectedMemberIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [form, setForm] = useState({ ...EMPTY_FORM });

  // ── Load projects & assignable users on mount ──────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projectData, userData] = await Promise.all([
        projectService.getProjects(),
        projectService.getAssignableUsers(),
      ]);
      setProjects(projectData);
      setAssignableUsers(userData);
    } catch (err: any) {
      setError('Failed to load project data. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleToggleMember = (userId: number) => {
    setSelectedMemberIds((prev) =>
      prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]
    );
  };

  // ── Create project — POST to backend DB ────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.location.trim() || !form.sqft || !form.floors) {
      setError('Please fill in all required fields.');
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const created = await projectService.createProject({
        name: form.name.trim(),
        location: form.location.trim(),
        sqft: Number(form.sqft),
        floors: Number(form.floors),
        structural_system: form.structural_system,
        member_ids: selectedMemberIds,
      });

      // Add to top of list immediately (optimistic update)
      setProjects((prev) => [created, ...prev]);
      setSuccessMsg(`✅ Project "${created.name}" created and saved to database!`);
      setForm({ ...EMPTY_FORM });
      setSelectedMemberIds([]);

      // Auto-clear success message after 5 seconds
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Failed to create project. Please try again.';
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">

      {/* ── Create New Project Form ── */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-[#C28E64] p-2.5 rounded-xl text-white">
            <PlusCircle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-stone-900">Create New Construction Project</h3>
            <p className="text-xs text-stone-500">Register new job site and assign field team members</p>
          </div>
        </div>

        {/* Feedback messages */}
        {error && (
          <div className="mb-4 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-xs font-semibold px-4 py-3 rounded-xl">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}
        {successMsg && (
          <div className="mb-4 flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold px-4 py-3 rounded-xl">
            <CheckCircle className="w-4 h-4 shrink-0" />
            {successMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">

            {/* Project Name */}
            <div>
              <label className="block font-bold text-stone-700 mb-1">Project Name <span className="text-red-500">*</span></label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-white text-stone-900 font-medium border border-stone-300 rounded-xl focus:ring-2 focus:ring-[#C28E64] focus:outline-none placeholder-stone-400"
                placeholder="e.g. Austin Commercial Tower C"
              />
            </div>

            {/* Location */}
            <div>
              <label className="block font-bold text-stone-700 mb-1">US Location <span className="text-red-500">*</span></label>
              <input
                type="text"
                required
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-white text-stone-900 font-medium border border-stone-300 rounded-xl focus:ring-2 focus:ring-[#C28E64] focus:outline-none placeholder-stone-400"
                placeholder="e.g. Austin, Texas, US"
              />
            </div>

            {/* Covered Area */}
            <div>
              <label className="block font-bold text-stone-700 mb-1">Covered Area (sqft) <span className="text-red-500">*</span></label>
              <input
                type="number"
                required
                min={100}
                value={form.sqft}
                onChange={(e) => setForm({ ...form, sqft: e.target.value as unknown as number })}
                className="w-full px-3.5 py-2.5 bg-white text-stone-900 font-medium border border-stone-300 rounded-xl focus:ring-2 focus:ring-[#C28E64] focus:outline-none placeholder-stone-400"
                placeholder="55000"
              />
            </div>

            {/* Number of Floors */}
            <div>
              <label className="block font-bold text-stone-700 mb-1">Number of Floors <span className="text-red-500">*</span></label>
              <input
                type="number"
                required
                min={1}
                value={form.floors}
                onChange={(e) => setForm({ ...form, floors: e.target.value as unknown as number })}
                className="w-full px-3.5 py-2.5 bg-white text-stone-900 font-medium border border-stone-300 rounded-xl focus:ring-2 focus:ring-[#C28E64] focus:outline-none placeholder-stone-400"
                placeholder="8"
              />
            </div>

            {/* Structural System */}
            <div>
              <label className="block font-bold text-stone-700 mb-1">Structural System</label>
              <select
                value={form.structural_system}
                onChange={(e) => setForm({ ...form, structural_system: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-white text-stone-900 font-medium border border-stone-300 rounded-xl focus:ring-2 focus:ring-[#C28E64] focus:outline-none"
              >
                {STRUCTURAL_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>

          </div>

          {/* Assign Team Members Checkboxes */}
          <div className="pt-2">
            <label className="block font-bold text-stone-700 mb-2 text-xs flex items-center gap-1.5">
              <Users className="w-4 h-4 text-[#C28E64]" />
              <span>Assign Active Team Members</span>
            </label>
            {assignableUsers.length === 0 ? (
              <p className="text-stone-400 text-xs italic">No active users available for assignment.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {assignableUsers.map((user) => {
                  const isSelected = selectedMemberIds.includes(user.id);
                  return (
                    <button
                      key={user.id}
                      type="button"
                      onClick={() => handleToggleMember(user.id)}
                      className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-2 transition ${
                        isSelected
                          ? 'bg-[#C28E64]/10 border-[#C28E64] text-[#C28E64]'
                          : 'bg-stone-50 border-stone-200 text-stone-600 hover:bg-stone-100'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}} // Handled by button click
                        className="rounded text-[#C28E64] focus:ring-[#C28E64]"
                      />
                      <span>{user.full_name} ({user.role})</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="bg-[#C28E64] hover:bg-[#A8754F] disabled:opacity-60 disabled:cursor-not-allowed text-white px-6 py-2.5 rounded-xl font-bold transition shadow-md flex items-center space-x-2 text-xs"
            >
              {submitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <PlusCircle className="w-4 h-4" />
              )}
              <span>{submitting ? 'Saving to Database...' : 'Create Project & Assign Members'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* ── Active Projects Table ── */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-stone-900">Active Managed Construction Projects</h3>
            <p className="text-xs text-stone-500">Live project tracking and team member allocations — persisted to database</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              disabled={loading}
              title="Refresh projects"
              className="p-2 rounded-xl border border-stone-200 text-stone-500 hover:text-[#C28E64] hover:border-[#C28E64] transition"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <span className="bg-[#C28E64]/10 text-[#C28E64] font-bold text-xs px-3.5 py-1.5 rounded-full border border-[#C28E64]/20">
              {projects.length} Active Project{projects.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-stone-400">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            <span className="text-sm">Loading projects from database...</span>
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-12 text-stone-400 text-sm">
            <p className="font-semibold">No active projects yet.</p>
            <p className="text-xs mt-1">Create your first project using the form above.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-stone-200 text-[11px] font-bold text-stone-400 uppercase tracking-wider">
                  <th className="py-3 px-3">Project Name</th>
                  <th className="py-3 px-3">Location</th>
                  <th className="py-3 px-3">Sqft / Floors</th>
                  <th className="py-3 px-3">Structural System</th>
                  <th className="py-3 px-3">Assigned Members</th>
                  <th className="py-3 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 text-xs">
                {projects.map((p) => (
                  <tr key={p.id} className="hover:bg-stone-50 transition">
                    <td className="py-4 px-3 font-bold text-stone-900">{p.name}</td>
                    <td className="py-4 px-3 text-stone-600 font-medium">{p.location}</td>
                    <td className="py-4 px-3 text-stone-700 font-mono">
                      {Number(p.sqft).toLocaleString()} sqft ({p.floors} Floors)
                    </td>
                    <td className="py-4 px-3 text-stone-600">{p.structural_system}</td>
                    <td className="py-4 px-3">
                      <div className="flex flex-wrap gap-1">
                        {(p.members || []).map((member, idx) => (
                          <span
                            key={member.user_id || idx}
                            className="bg-stone-100 text-stone-800 px-2.5 py-1 rounded-lg border border-stone-200 text-[11px] font-semibold"
                          >
                            {typeof member === 'string' ? member : member.full_name}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-4 px-3">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                        <CheckCircle className="w-3 h-3 text-emerald-600" />
                        <span>{p.status}</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
};

