import { ChatMessage } from '@/lib/types';

interface MessageBubbleProps {
  message: ChatMessage;
}

function renderMarkdown(text: string): string {
  let html = text;

  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/`(.*?)`/g, '<code class="bg-arctic-soft border border-slopes/30 text-mountainside px-1.5 py-0.5 rounded text-xs font-mono">$1</code>');
  html = html.replace(/\n/g, '<br />');

  return html;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 items-start gap-2.5`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-midnight border border-mountainside text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-2xs">
          ✨
        </div>
      )}
      <div
        className={`max-w-[78%] sm:max-w-[70%] rounded-2xl px-4.5 py-3 shadow-xs ${
          isUser
            ? 'bg-midnight text-white border border-mountainside'
            : 'bg-white text-midnight border border-slopes/40'
        }`}
      >
        <div
          className="text-sm leading-relaxed"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
        />
        <p
          className={`text-[10px] mt-1.5 font-medium ${
            isUser ? 'text-slopes text-right' : 'text-apres'
          }`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-xl bg-mountainside border border-slopes/30 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-2xs">
          👤
        </div>
      )}
    </div>
  );
}
