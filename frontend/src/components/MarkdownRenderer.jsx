/**
 * Markdown Renderer Component
 * 
 * Converts markdown formatting in text to styled JSX:
 * - **text** → <strong>text</strong> (bold)
 * - *text* → <em>text</em> (italic)
 * - `code` → <code>code</code> (inline code)
 * - [text](url) → <a>text</a> (links)
 * 
 * Processes patterns in order: links → bold → italic → code
 */

export default function MarkdownRenderer({ text }) {
  if (!text || typeof text !== 'string') {
    return <span>{text}</span>;
  }

  // Parse markdown into an array of { type, content }
  const parseMarkdown = (str) => {
    const tokens = [];
    let i = 0;

    while (i < str.length) {
      // Check for link [text](url)
      const linkMatch = str.slice(i).match(/^\[([^\]]+)\]\(([^)]+)\)/);
      if (linkMatch) {
        tokens.push({ type: 'link', text: linkMatch[1], url: linkMatch[2] });
        i += linkMatch[0].length;
        continue;
      }

      // Check for bold **text**
      const boldMatch = str.slice(i).match(/^\*\*([^\*]+)\*\*/);
      if (boldMatch) {
        tokens.push({ type: 'bold', text: boldMatch[1] });
        i += boldMatch[0].length;
        continue;
      }

      // Check for italic *text* (but not **)
      const italicMatch = str.slice(i).match(/^\*([^\*]+)\*(?!\*)/);
      if (italicMatch) {
        tokens.push({ type: 'italic', text: italicMatch[1] });
        i += italicMatch[0].length;
        continue;
      }

      // Check for code `text`
      const codeMatch = str.slice(i).match(/^`([^`]+)`/);
      if (codeMatch) {
        tokens.push({ type: 'code', text: codeMatch[1] });
        i += codeMatch[0].length;
        continue;
      }

      // Regular text: consume until next special char
      const nextSpecial = str.slice(i).search(/[\[\*`]/);
      if (nextSpecial === -1) {
        tokens.push({ type: 'text', text: str.slice(i) });
        break;
      } else {
        tokens.push({ type: 'text', text: str.slice(i, i + nextSpecial) });
        i += nextSpecial;
      }
    }

    return tokens;
  };

  const tokens = parseMarkdown(text);

  return (
    <span className="whitespace-pre-wrap">
      {tokens.map((token, idx) => {
        if (token.type === 'bold') {
          return (
            <strong key={idx} className="font-semibold text-white">
              {token.text}
            </strong>
          );
        }

        if (token.type === 'italic') {
          return (
            <em key={idx} className="italic text-slate-300">
              {token.text}
            </em>
          );
        }

        if (token.type === 'code') {
          return (
            <code
              key={idx}
              className="bg-[#1A1A24] border border-white/10 px-1.5 py-0.5 rounded text-xs font-mono text-indigo-400"
            >
              {token.text}
            </code>
          );
        }

        if (token.type === 'link') {
          return (
            <a
              key={idx}
              href={token.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 underline transition-colors"
            >
              {token.text}
            </a>
          );
        }

        return <span key={idx}>{token.text}</span>;
      })}
    </span>
  );
}
