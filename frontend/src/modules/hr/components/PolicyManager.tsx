'use client';

import React, { useState } from 'react';
import { CompanyPolicy } from '@/core/types';
import { hrService } from '../services/hrService';
import { BookOpen, Upload, Trash2, FileText, CheckCircle2, FileUp } from 'lucide-react';

interface PolicyManagerProps {
  policies: CompanyPolicy[];
  onRefresh: () => void;
}

export const PolicyManager: React.FC<PolicyManagerProps> = ({ policies, onRefresh }) => {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('General');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!['pdf', 'docx', 'txt'].includes(ext || '')) {
        setErrorMsg('Invalid file format. Only PDF, DOCX, and TXT files are supported.');
        setSelectedFile(null);
        return;
      }
      setErrorMsg('');
      setSelectedFile(file);
    }
  };

  const handleUploadPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg('Please select a document file (.pdf, .docx, or .txt).');
      return;
    }

    setLoading(true);
    setErrorMsg('');

    try {
      const formData = new FormData();
      formData.append('title', title);
      formData.append('category', category);
      formData.append('file', selectedFile);

      await hrService.uploadPolicyDocument(formData);
      setTitle('');
      setCategory('General');
      setSelectedFile(null);
      onRefresh();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to upload policy document.';
      setErrorMsg(msg);
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

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* Upload Company Policy Document Form */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center space-x-3 mb-4">
          <div className="bg-[#C28E64] p-2.5 rounded-xl text-white">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-stone-900">Upload Company Policy Document</h3>
            <p className="text-xs text-stone-500">
              Upload official HR policy documents (.PDF, .DOCX, .TXT) to index in the policy metadata repository
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs font-semibold">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleUploadPolicy} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-stone-700 mb-1">Document Title</label>
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
            <label className="block text-xs font-bold text-stone-700 mb-1">Choose Policy Document (PDF / DOCX / TXT)</label>
            <div className="border-2 border-dashed border-stone-300 hover:border-[#C28E64] rounded-2xl p-6 text-center transition bg-stone-50 cursor-pointer relative">
              <input
                type="file"
                required
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="flex flex-col items-center justify-center space-y-2">
                <FileUp className="w-8 h-8 text-[#C28E64]" />
                <span className="text-sm font-semibold text-stone-700">
                  {selectedFile ? selectedFile.name : 'Click or Drag & Drop Policy File Here'}
                </span>
                <span className="text-xs text-stone-400">
                  Supported formats: .pdf, .docx, .txt (Max size: 10MB)
                </span>
                {selectedFile && (
                  <span className="inline-flex items-center space-x-1 text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})</span>
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading || !selectedFile}
              className="bg-[#C28E64] hover:bg-[#A8754F] disabled:opacity-50 text-white px-6 py-2.5 rounded-xl font-bold text-sm shadow transition flex items-center space-x-2"
            >
              <Upload className="w-4 h-4" />
              <span>{loading ? 'Uploading Document...' : 'Upload Document'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Policy Documents List */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-stone-900">Company Policy Document Repository</h3>
            <p className="text-xs text-stone-500">
              Uploaded document metadata registered in Buildora SQLite storage
            </p>
          </div>
          <span className="bg-stone-100 text-stone-700 font-bold text-xs px-3 py-1 rounded-full border border-stone-200">
            {policies.length} Documents Active
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {policies.map((p) => (
            <div key={p.id} className="bg-stone-50 p-4 rounded-2xl border border-stone-200 flex flex-col justify-between space-y-3">
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

                <div className="bg-white p-3 rounded-xl border border-stone-200 space-y-1.5 text-xs text-stone-600">
                  {p.original_filename ? (
                    <>
                      <div className="flex justify-between">
                        <span className="text-stone-400 font-medium">Original File:</span>
                        <span className="font-semibold text-stone-800 truncate max-w-[180px]">{p.original_filename}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-stone-400 font-medium">Format / Size:</span>
                        <span className="font-semibold text-stone-800">{p.file_type || 'N/A'} • {formatFileSize(p.file_size)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-stone-400 font-medium">Index Status:</span>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800">
                          {p.index_status || 'UPLOADED'} (Chunks: {p.chunk_count ?? 0})
                        </span>
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-stone-600 leading-relaxed italic">
                      {p.content || 'Legacy policy text record'}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex justify-between items-center pt-2 border-t border-stone-200">
                <span className="text-[10px] text-stone-400">
                  Uploaded: {new Date(p.created_at).toLocaleDateString()}
                </span>
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
