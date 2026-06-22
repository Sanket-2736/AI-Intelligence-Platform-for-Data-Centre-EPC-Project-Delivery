import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Send, Zap, FileText } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import LoadingSpinner from '../components/LoadingSpinner';
import MarkdownRenderer from '../components/MarkdownRenderer';
import { rfiApi } from '../api/client';

export default function RFIAgent() {
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [responseTime, setResponseTime] = useState(null);
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

  const handleFileSelect = async (file) => {
    if (!file) return;

    try {
      const response = await rfiApi.ingestBatch([file]);
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
    <div className="flex h-full gap-6 p-6 bg-[#0A0A0F]">
      {/* Left Panel - Document Library */}
      <div className="w-80 bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6 flex flex-col">
        <h2 className="text-sm font-semibold text-white mb-5 flex items-center gap-2">
          <FileText size={16} className="text-indigo-400" />
          Document Library
        </h2>

        {/* Upload Section */}
        <div className="mb-6">
          <label className="section-title">Upload Documents</label>
          <FileUpload
            accept=".pdf"
            onUpload={handleFileSelect}
            label="Drop PDFs here or click to upload"
          />
        </div>

        {/* Doc Type Filter */}
        <div className="mb-5">
          <label className="section-title">Document Type</label>
          <select
            value={docTypeFilter}
            onChange={(e) => setDocTypeFilter(e.target.value)}
            className="input-field w-full"
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
          <p className="text-xs text-slate-600 mb-3">
            {documents.length} documents indexed
          </p>
          {documents.length > 0 ? (
            documents.map((doc, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 p-2.5 rounded-lg hover:bg-white/5 transition-colors group cursor-pointer"
              >
                <FileText size={14} className="text-slate-500 flex-shrink-0 group-hover:text-indigo-400 transition-colors" />
                <div className="flex-1 min-w-0">
                  <p className="text-slate-300 text-sm truncate">{doc.filename}</p>
                </div>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex-shrink-0">
                  {doc.doc_type || 'Doc'}
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-slate-600 text-center py-8">
              No documents yet. Upload to get started.
            </p>
          )}
        </div>
      </div>

      {/* Right Panel - Chat Interface */}
      <div className="flex-1 bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6 flex flex-col">
        <h2 className="text-sm font-semibold text-white mb-5 flex items-center gap-2">
          <MessageSquare size={16} className="text-indigo-400" />
          Ask Project Documents
        </h2>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto mb-4 space-y-4 pr-2">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-center">
              <div>
                <MessageSquare size={48} className="mx-auto mb-3 text-slate-700" />
                <p className="text-slate-600 text-sm">
                  Upload documents and ask questions about your project
                </p>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx}>
                {msg.type === 'user' ? (
                  <div className="flex justify-end mb-3">
                    <div className="bg-indigo-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm max-w-[80%]">
                      {msg.text}
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-start mb-3">
                    <div className="bg-[#1A1A24] border border-white/5 text-slate-200 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm max-w-[85%]">
                      <MarkdownRenderer text={msg.text} />
                      {Array.isArray(msg.citations) && msg.citations.length > 0 && (
                        <div className="mt-3 space-y-1.5 border-t border-white/5 pt-2.5">
                          {msg.citations.map((citation, cidx) => (
                            <div key={citation?.source_id || cidx}>
                              <div className="text-xs text-indigo-400 font-medium mb-0.5">
                                [SOURCE {cidx + 1}] {citation?.filename || 'Unknown'}
                              </div>
                              <div className="flex items-center gap-2 text-xs text-slate-400">
                                {citation?.doc_type && (
                                  <span className="bg-white/5 px-1.5 py-0.5 rounded">
                                    {citation.doc_type}
                                  </span>
                                )}
                                {citation?.relevance_score && (
                                  <span className="bg-indigo-500/10 text-indigo-400 px-1.5 py-0.5 rounded">
                                    {(citation.relevance_score * 100).toFixed(0)}% match
                                  </span>
                                )}
                              </div>
                            </div>
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
            <div className="flex justify-start mb-3">
              <div className="bg-[#1A1A24] border border-white/5 rounded-2xl rounded-bl-sm px-4 py-2.5">
                <LoadingSpinner size="sm" message="Analysing documents..." />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Response Time Indicator */}
        {responseTime && (
          <div className="bg-[#0D0D14] border-t border-white/5 px-0 py-3 text-xs text-slate-500 flex items-center gap-2 mb-4">
            <Zap size={14} className="text-amber-400" />
            Answered in {responseTime}s (Cerebras llama-3.3-70b)
          </div>
        )}

        {/* Input Area */}
        <form onSubmit={handleSendMessage} className="flex gap-2.5">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask a question about your project documents..."
            className="textarea-field flex-1"
            rows="3"
          />
          <button
            type="submit"
            disabled={loading || !inputValue.trim()}
            className="px-3 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:opacity-50 rounded-xl text-white font-medium flex items-center justify-center transition-colors flex-shrink-0"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}