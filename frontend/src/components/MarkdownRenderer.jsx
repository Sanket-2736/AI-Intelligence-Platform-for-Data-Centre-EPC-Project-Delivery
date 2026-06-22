/**
 * Markdown Renderer Component - Optimized for Large Content
 * 
 * Converts markdown formatting in text to styled JSX using regex replace:
 * - **text** → <strong>text</strong> (bold)
 * - *text* → <em>text</em> (italic)
 * - `code` → <code>code</code> (inline code)
 * - [text](url) → <a>text</a> (links)
 * 
 * Uses simple regex replacement instead of token parsing for better performance
 * with large response bodies. No loop-based parsing = no hanging.
 */

export default function MarkdownRenderer({ text }) {
  if (!text || typeof text !== 'string') {
    return <span>{text}</span>;
  }

  // Simple regex-based replacement: process each pattern once
  // This avoids tokenization loops that can hang on large content
  
  // Process: bold → italic → code → links → split and render
  let processed = text;

  // 1. Handle bold **text** (non-greedy)
  processed = processed.replace(/\*\*(.+?)\*\*/g, '<BOLD>$1</BOLD>');

  // 2. Handle italic *text* (but not ** or ***)
  // Use negative lookbehind/lookahead to avoid matching ** edges
  processed = processed.replace(/\*([^\*].+?[^\*])\*/g, '<ITALIC>$1</ITALIC>');

  // 3. Handle inline code `text`
  processed = processed.replace(/`([^`]+)`/g, '<CODE>$1</CODE>');

  // 4. Handle links [text](url)
  processed = processed.replace(/\[([^\]]+)\]\(([^\)]+)\)/g, '<LINK|$1|$2</LINK>');

  // Split by our markers and render
  const parts = processed.split(/(<BOLD>.*?<\/BOLD>|<ITALIC>.*?<\/ITALIC>|<CODE>.*?<\/CODE>|<LINK\|.*?\<\/LINK>)/);

  return (
    <div className="overflow-x-hidden break-words">
      {parts.map((part, idx) => {
        if (!part) return null;

        // Handle bold
        if (part.startsWith('<BOLD>') && part.endsWith('</BOLD>')) {
          const content = part.slice(6, -7);
          return (
            <strong key={idx} className="font-semibold text-white">
              {content}
            </strong>
          );
        }

        // Handle italic
        if (part.startsWith('<ITALIC>') && part.endsWith('</ITALIC>')) {
          const content = part.slice(8, -9);
          return (
            <em key={idx} className="italic text-slate-300">
              {content}
            </em>
          );
        }

        // Handle code
        if (part.startsWith('<CODE>') && part.endsWith('</CODE>')) {
          const content = part.slice(6, -7);
          return (
            <code
              key={idx}
              className="bg-[#1A1A24] border border-white/10 px-1.5 py-0.5 rounded text-xs font-mono text-indigo-400"
            >
              {content}
            </code>
          );
        }

        // Handle links
        if (part.startsWith('<LINK|') && part.endsWith('</LINK>')) {
          const content = part.slice(6, -7);
          const [linkText, url] = content.split('|');
          return (
            <a
              key={idx}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 underline transition-colors"
            >
              {linkText}
            </a>
          );
        }

        // Plain text
        return <span key={idx}>{part}</span>;
      })}
    </div>
  );
}
