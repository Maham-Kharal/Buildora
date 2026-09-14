'use client';

import React, { useState } from 'react';
import { UploadCloud, CheckCircle, Sparkles, AlertCircle, FileText } from 'lucide-react';
import { userService } from '../services/userService';
import { Receipt } from '@/core/types';

interface ReceiptUploaderProps {
  onSuccess: (newReceipt: Receipt) => void;
}

export const ReceiptUploader: React.FC<ReceiptUploaderProps> = ({ onSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [ocrResult, setOcrResult] = useState<Receipt | null>(null);
  const [error, setError] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
      setOcrResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');

    try {
      const receipt = await userService.uploadReceipt(file);
      setOcrResult(receipt);
      onSuccess(receipt);
      setFile(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to analyze and save receipt image.');
    } finally {
      setUploading(false);
    }
  };

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

      {/* Drag & Drop Box */}
      <div className="border-2 border-dashed border-stone-300 rounded-2xl p-6 text-center hover:border-[#C28E64] transition bg-stone-50/50">
        <input
          type="file"
          accept="image/*"
          id="receipt-file"
          className="hidden"
          onChange={handleFileChange}
        />
        <label htmlFor="receipt-file" className="cursor-pointer flex flex-col items-center">
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
          disabled={uploading}
          className="mt-4 w-full bg-[#C28E64] hover:bg-[#A8754F] text-white py-3 rounded-xl font-bold text-sm shadow transition flex items-center justify-center space-x-2"
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
              <span className="text-stone-400 block font-medium">Vendor</span>
              <span className="font-bold text-stone-800">{ocrResult.vendor_name}</span>
            </div>
            <div className="bg-white p-2.5 rounded-xl border border-emerald-100">
              <span className="text-stone-400 block font-medium">Total USD</span>
              <span className="font-bold text-emerald-700">${ocrResult.total_amount.toFixed(2)}</span>
            </div>
            <div className="bg-white p-2.5 rounded-xl border border-emerald-100">
              <span className="text-stone-400 block font-medium">Category</span>
              <span className="font-semibold text-stone-800">{ocrResult.category || 'Materials'}</span>
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
