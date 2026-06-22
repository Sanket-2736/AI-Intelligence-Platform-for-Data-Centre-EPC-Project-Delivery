/**
 * File Upload Component
 * Reusable file upload handler for documents and schedules
 */

import { useState } from 'react';
import { Upload } from 'lucide-react';

export default function FileUpload({ onUpload, accept = '.pdf,.xlsx,.csv' }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

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
      try {
        await onUpload(file);
      } catch (error) {
        console.error('Upload error:', error);
      }
    }
    setIsLoading(false);
  };

  return (
    <div
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-lg p-8 text-center transition ${
        isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
      }`}
    >
      <Upload className="mx-auto mb-3 text-gray-400" size={32} />
      <p className="mb-2 font-semibold text-gray-700">Drop files here or click to upload</p>
      <input
        type="file"
        multiple
        accept={accept}
        onChange={handleFileInputChange}
        disabled={isLoading}
        className="hidden"
        id="file-input"
      />
      <label htmlFor="file-input" className="btn-primary cursor-pointer inline-block">
        {isLoading ? 'Uploading...' : 'Select Files'}
      </label>
    </div>
  );
}
