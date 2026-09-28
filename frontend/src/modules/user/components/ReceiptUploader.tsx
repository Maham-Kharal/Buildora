'use client';

import React, { useState, useEffect } from 'react';
import { UploadCloud, CheckCircle, Sparkles, AlertCircle, FileText, Building2 } from 'lucide-react';
import { userService } from '../services/userService';
import { Receipt, AssignedProject } from '@/core/types';

interface ReceiptUploaderProps {
  onSuccess: (newReceipt: Receipt) => void;
}

export const ReceiptUploader: React.FC<ReceiptUploaderProps> = ({ onSuccess }) => {
  const [assignedProjects, setAssignedProjects] = useState<AssignedProject[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [selectedProjectId, setSelectedProjectId] = useState<number | ''>('');

  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [ocrResult, setOcrResult] = useState<Receipt | null>(null);
  const [error, setError] = useState('');

  // Fetch assigned active projects on component mount
  useEffect(() => {
    let isMounted = true;
    const fetchProjects = async () => {
      setLoadingProjects(true);
      try {
        const projects = await userService.getAssignedProjects();
        if (isMounted) {
          setAssignedProjects(projects);
          if (projects.length === 1) {
            setSelectedProjectId(projects[0].id);
          }
        }
      } catch (err) {
        if (isMounted) {
          setError('Failed to load assigned construction projects.');
        }
      } finally {
        if (isMounted) {
          setLoadingProjects(false);
        }
      }
    };
    fetchProjects();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
      setOcrResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a receipt image file.');
      return;
    }
    if (!selectedProjectId) {
      setError('Please select an assigned active project before uploading.');
      return;
    }

    setUploading(true);
    setError('');

    try {
      const receipt = await userService.uploadReceipt(file, Number(selectedProjectId));
      setOcrResult(receipt);
      onSuccess(receipt);
      setFile(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to analyze and save receipt image.');
    } finally {
      setUploading(false);
    }
  };

  const hasNoProjects = !loadingProjects && assignedProjects.length === 0;

  return (
    <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
      <div className="flex items-center space-x-3 mb-4">
        <div className="bg-[#C28E64]/10 p-2.5 rounded-xl text-[#C28E64]">
          <UploadCloud className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-stone-900">Submit Construction Expense Receipt</h3>
          <p className="text-xs text-stone-500">
            Upload photo of physical receipt ($0 local storage + Gemini AI Vision OCR)
          </p>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-xs p-3 rounded-xl flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* No assigned projects warning message */}
      {hasNoProjects && (
        <div className="mb-4 bg-amber-50 border border-amber-200 text-amber-800 text-xs p-3.5 rounded-xl flex items-start space-x-2 font-medium">
          <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
          <span>
            You are not currently assigned to an active project. Contact an administrator before uploading a project receipt.
          </span>
        </div>
      )}

      {/* Project Selection Dropdown */}
      <div className="mb-4 text-xs">
        <label className="block font-bold text-stone-700 mb-1 flex items-center gap-1.5">
          <Building2 className="w-3.5 h-3.5 text-[#C28E64]" />
          <span>Assigned Construction Project <span className="text-red-500">*</span></span>
        </label>
        <select
          value={selectedProjectId}
          onChange={(e) => {
            setSelectedProjectId(e.target.value ? Number(e.target.value) : '');
            setError('');
          }}
          disabled={loadingProjects || hasNoProjects}
          className="w-full px-3.5 py-2.5 bg-white text-stone-900 font-medium border border-stone-300 rounded-xl focus:ring-2 focus:ring-[#C28E64] focus:outline-none disabled:opacity-60 disabled:bg-stone-100"
        >
          <option value="">-- Select Assigned Active Project --</option>
          {assignedProjects.map((proj) => (
            <option key={proj.id} value={proj.id}>
              {proj.name}
            </option>
          ))}
        </select>
      </div>

      {/* Drag & Drop Box */}
      <div
        className={`border-2 border-dashed rounded-2xl p-6 text-center transition bg-stone-50/50 ${
          hasNoProjects ? 'opacity-50 border-stone-200 cursor-not-allowed' : 'border-stone-300 hover:border-[#C28E64]'
        }`}
      >
        <input
          type="file"
          accept="image/*"
          id="receipt-file"
          className="hidden"
          disabled={hasNoProjects}
          onChange={handleFileChange}
        />
        <label
          htmlFor={hasNoProjects ? undefined : 'receipt-file'}
          className={`${hasNoProjects ? 'cursor-not-allowed' : 'cursor-pointer'} flex flex-col items-center`}
        >
          <FileText className="w-10 h-10 text-stone-400 mb-2" />
          <span className="text-sm font-semibold text-stone-700 mb-1">
            {file ? file.name : 'Click to upload receipt image'}
          </span>
          <span className="text-xs text-stone-400">PNG, JPG, JPEG up to 10MB</span>
        </label>
      </div>

      {/* Upload Button */}
      {file && (
        <button
          onClick={handleUpload}
          disabled={uploading || !selectedProjectId || hasNoProjects}
          className="mt-4 w-full bg-[#C28E64] hover:bg-[#A8754F] disabled:opacity-50 disabled:cursor-not-allowed text-white py-3 rounded-xl font-bold text-sm shadow transition flex items-center justify-center space-x-2"
        >
          <Sparkles className="w-4 h-4" />
          <span>{uploading ? 'Analyzing with Gemini Vision OCR...' : 'Process & Submit Receipt'}</span>
        </button>
      )}

      {/* Gemini OCR Result Preview Card */}
      {ocrResult && (
        <div className="mt-6 bg-emerald-50/80 border border-emerald-200 rounded-2xl p-4 animate-fade-in">
          <div className="flex items-center space-x-2 text-emerald-800 font-bold text-sm mb-3">
            <CheckCircle className="w-5 h-5 text-emerald-600" />
            <span>Gemini Vision OCR Extraction Complete</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
            <div className="bg-white p-2.5 rounded-xl border border-emerald-100">
              <span className="text-stone-400 block font-medium">Project</span>
              <span className="font-bold text-stone-800">{ocrResult.project_name || 'Assigned Project'}</span>
            </div>
            <div className="bg-white p-2.5 rounded-xl border border-emerald-100">
              <span className="text-stone-400 block font-medium">Vendor</span>
              <span className="font-bold text-stone-800">{ocrResult.vendor_name}</span>
            </div>
            <div className="bg-white p-2.5 rounded-xl border border-emerald-100">
              <span className="text-stone-400 block font-medium">Total USD</span>
              <span className="font-bold text-emerald-700">${ocrResult.total_amount.toFixed(2)}</span>
            </div>
            <div className="bg-white p-2.5 rounded-xl border border-emerald-100">
              <span className="text-stone-400 block font-medium">Status</span>
              <span className="font-bold text-amber-600">{ocrResult.status}</span>
            </div>
          </div>

          {/* Line items list */}
          {ocrResult.items && ocrResult.items.length > 0 && (
            <div className="bg-white rounded-xl p-3 border border-emerald-100">
              <span className="text-[11px] font-bold text-stone-500 uppercase tracking-wider block mb-2">
                Parsed Line Items:
              </span>
              <div className="space-y-1.5 text-xs">
                {ocrResult.items.map((item, idx) => (
                  <div key={idx} className="flex justify-between items-center text-stone-700">
                    <span>
                      {item.item_name} <span className="text-stone-400">(x{item.quantity})</span>
                    </span>
                    <span className="font-mono font-semibold">${item.total_price.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

