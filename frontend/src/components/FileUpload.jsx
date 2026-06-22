/**
 * File Upload Component (Premium Design)
 * Reusable file upload handler with modern styling
 */

import { useState } from 'react';
import { Upload, X, FileText } from 'lucide-react';

export default function FileUpload({ onUpload, accept = '.pdf,.xlsx,.csv' }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const handleDragEnter = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = async (files) => {
    setIsLoading(true);
    for (const file of files) {
      setSelectedFile(file);
      try {
        await onUpload(file);
      } catch (error) {
        console.error('Upload error:', error);
      }
    }
    setIsLoading(false);
    setSelectedFile(null);
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes, k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="space-y-3">
      {selectedFile ? (
        <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-xl p-3 flex items-center gap-3">
          <FileText size={18} className="text-indigo-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-slate-300 text-sm font-medium truncate">
              {selectedFile.name}
            </p>
            <p className="text-slate-500 text-xs">
              {formatFileSize(selectedFile.size)}
            </p>
          </div>
          <button
            onClick={() => setSelectedFile(null)}
            disabled={isLoading}
            className="p-1 rounded-lg hover:bg-indigo-500/20 transition-colors flex-shrink-0"
          >
            <X size={16} className="text-indigo-400" />
          </button>
        </div>
      ) : (
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`
            border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer
            ${
              isDragging
                ? 'border-indigo-500/50 bg-indigo-500/5'
                : 'border-white/10 hover:border-indigo-500/50 hover:bg-indigo-500/5'
            }
          `}
        >
          <Upload className={`mx-auto mb-3 ${isDragging ? 'text-indigo-400' : 'text-slate-500'}`} size={32} />
          <p className="mb-2 font-medium text-slate-200">Drop PDFs here or click to upload</p>
          <input
            type="file"
            multiple
            accept={accept}
            onChange={handleFileInputChange}
            disabled={isLoading}
            className="hidden"
            id="file-input"
          />
          <label
            htmlFor="file-input"
            className="inline-block px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg cursor-pointer transition-colors"
          >
            {isLoading ? 'Uploading...' : 'Select Files'}
          </label>
        </div>
      )}
    </div>
  );
}
