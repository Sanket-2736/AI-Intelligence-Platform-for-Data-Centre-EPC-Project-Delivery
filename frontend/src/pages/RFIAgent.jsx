/**
 * RFI Intelligence Agent Page
 * 
 * Two-panel layout:
 * - LEFT: Document library with upload and indexed docs list
 * - RIGHT: Chat interface with message history, citations, and input
 */

import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Upload, Send, Zap } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import LoadingSpinner from '../components/LoadingSpinner';
import { rfiApi } from '../api/client';

export default function RFIAgent() {
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [responseTime, setResponseTime] = useState(null);
  const [ingestingFiles, setIngestingFiles] = useState(false);
  const [docTypeFilter, setDocTypeFilter] = useState('Specification');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadHistory();
    loadDocuments();
  }, []);

  const loadHistory = async () => {
    try {
      const response = await rfiApi.getHistory(5);
      if (response.data?.rfis) {
        const formattedMessages = response.data.rfis.flatMap((rfi) => [
          { type: 'user', text: rfi.question },
          {
            type: 'ai',
            text: rfi.answer,
            citations: rfi.citations_json ? JSON.parse(rfi.citations_json) : [],
          },
        ]);
        setMessages(formattedMessages);
      }
    } catch (error) {
      console.error('Error loading history:', error);
    }
  };

  const loadDocuments = async () => {
    try {
      const response = await rfiApi.getDocuments();
      if (response.data?.documents) {
        setDocuments(response.data.documents);
      }
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  };

  const handleFileSelect = async (files) => {
    if (files.length === 0) return;

    setIngestingFiles(true);
    try {
      const response = await rfiApi.ingestBatch(files);
      const result = response.data;

      // Show ingestion result
      setMessages((prev) => [
        ...prev,
        {
          type: 'ai',
          text: `✓ ${result.total_chunks || 0} chunks indexed from ${result.successful_files || 0} files`,
        },
      ]);

      // Reload documents
      loadDocuments();
    } catch (error) {
      console.error('Error ingesting files:', error);
      setMessages((prev) => [
        ...prev,
        { type: 'ai', text: '❌ Failed to ingest documents. Please try again.' },
      ]);
    } finally {
      setIngestingFiles(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const userMessage = inputValue;
    setInputValue('');
    setMessages((prev) => [...prev, { type: 'user', text: userMessage }]);
    setLoading(true);

    const startTime = Date.now();

    try {
      const response = await rfiApi.query(userMessage);
      const result = response.data;

      setResponseTime(((Date.now() - startTime) / 1000).toFixed(1));

      setMessages((prev) => [
        ...prev,
        {
          type: 'ai',
          text: result.answer,
          citations: result.citations || [],
        },
      ]);
    } catch (error) {
      console.error('Error querying RFI:', error);
      setMessages((prev) => [
        ...prev,
        { type: 'ai', text: '❌ Error querying documents. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full gap-6 p-6">
      {/* Left Panel - Document Library */}
      <div className="w-1/3 bg-gray-800 border border-gray-700 rounded-xl p-6 flex flex-col">
        <h2 className="text-xl font-bold mb-4">📁 Document Library</h2>

        {/* Upload Section */}
        <div className="mb-6">
          <label className="text-sm font-semibold text-gray-300 mb-2 block">
            Upload Documents
          </label>
          <FileUpload
            accept=".pdf"
            multiple
            label="Drop PDFs here or click to upload"
            onFileSelect={handleFileSelect}
          />
        </div>

        {/* Doc Type Filter */}
        <div className="mb-4">
          <label className="text-xs font-semibold text-gray-400 mb-2 block">
            Document Type
          </label>
          <select
            value={docTypeFilter}
            onChange={(e) => setDocTypeFilter(e.target.value)}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white"
          >
            <option>Specification</option>
            <option>RFI</option>
            <option>Submittal</option>
            <option>Meeting Minutes</option>
            <option>Change Order</option>
            <option>Standard</option>
          </select>
        </div>

        {/* Documents List */}
        <div className="flex-1 overflow-y-auto space-y-2">
          <p className="text-xs text-gray-500 mb-3">
            {documents.length} documents indexed
          </p>
          {documents.length > 0 ? (
            documents.map((doc, idx) => (
              <div
                key={idx}
                className="p-3 bg-gray-700/50 rounded-lg border border-gray-600 text-sm"
              >
                <p className="font-medium text-white truncate">
                  {doc.filename}
                </p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs bg-blue-500/30 text-blue-300 px-2 py-1 rounded">
                    {doc.doc_type || 'Document'}
                  </span>
                  <span className="text-xs text-gray-400">
                    {doc.chunk_count || 0} chunks
                  </span>
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-gray-500 text-center py-6">
              No documents yet. Upload to get started.
            </p>
          )}
        </div>
      </div>

      {/* Right Panel - Chat Interface */}
      <div className="flex-1 bg-gray-800 border border-gray-700 rounded-xl p-6 flex flex-col">
        <h2 className="text-xl font-bold mb-4">💬 Ask Project Documents</h2>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto mb-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-center">
              <div>
                <MessageSquare size={48} className="mx-auto mb-2 text-gray-500" />
                <p className="text-gray-400">
                  Upload documents and ask questions about your project
                </p>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx}>
                {msg.type === 'user' ? (
                  <div className="flex justify-end mb-2">
                    <div className="max-w-md bg-blue-600 rounded-lg p-3 text-white text-sm">
                      {msg.text}
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-start">
                    <div className="max-w-md bg-gray-700 rounded-lg p-3 text-gray-200 text-sm">
                      {msg.text}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-3 space-y-1 border-t border-gray-600 pt-2">
                          {msg.citations.map((citation, cidx) => (
                            <button
                              key={cidx}
                              className="text-xs text-blue-400 hover:text-blue-300 block truncate"
                            >
                              [SOURCE {cidx + 1}] {citation}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-700 rounded-lg p-3">
                <LoadingSpinner size="sm" message="Analysing documents..." />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Response Time Indicator */}
        {responseTime && (
          <div className="text-xs text-gray-400 mb-2 flex items-center gap-1">
            <Zap size={14} className="text-purple-400" />
            Answered in {responseTime}s (Cerebras llama-3.3-70b)
          </div>
        )}

        {/* Input */}
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask a question about your project documents..."
            className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            rows="3"
          />
          <button
            type="submit"
            disabled={loading || !inputValue.trim()}
            className="px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded-lg text-white font-medium flex items-center gap-2 transition-colors"
          >
            <Send size={18} />
            Ask
          </button>
        </form>
      </div>
    </div>
  );
}
