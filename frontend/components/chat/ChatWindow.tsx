'use client';

import { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send } from 'lucide-react';
import { useCanvasStore } from '@/store/useCanvasStore';
import { AssetType, Message, useChatStore } from '@/store/useChatStore';

export default function ChatWindow() {
  const { setView, setIds, openCanvas } = useCanvasStore();
  const messages = useChatStore((state) => state.messages);
  const input = useChatStore((state) => state.input);
  const isProcessing = useChatStore((state) => state.isProcessing);
  const assetType = useChatStore((state) => state.assetType);
  const setInput = useChatStore((state) => state.setInput);
  const setIsProcessing = useChatStore((state) => state.setIsProcessing);
  const setAssetType = useChatStore((state) => state.setAssetType);
  const addMessage = useChatStore((state) => state.addMessage);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isProcessing]);

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  const applySuggestion = (text: string) => {
    setInput(text);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    addMessage(userMsg);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    setIsProcessing(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text, asset_type: assetType }),
      });

      if (!res.ok) throw new Error('API Error');
      const data = await res.json();
      
      if (data.system_action) {
        if (data.system_action.type === 'COMPARE') {
            setIds(data.system_action.ids);
            setView('COMPARISON', data); // Pass raw data containing quant/comparison bits
            openCanvas(data);
        }
      }
      
      addMessage({ id: Date.now().toString(), role: 'system', content: data.answer });
    } catch {
      addMessage({ id: Date.now().toString(), role: 'system', content: 'Error: Unable to reach MarketMind core. Make sure the server is running.' });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <>
      <header className="chat-header w-full absolute top-0 left-0 bg-transparent z-10">
        <h2>Research Session</h2>
      </header>

      <div ref={scrollRef} className="chat-history flex-1 pt-24 pb-32">
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.role === 'system' ? 'system-msg' : 'user-msg'}`}>
            <div className="msg-content">
              {msg.role === 'system' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
              {msg.id === '1' && (
                <div className="suggestions">
                  <button className="suggestion-btn" onClick={() => applySuggestion('How is Reliance Industries performing today?')}>Reliance Industries</button>
                  <button className="suggestion-btn" onClick={() => applySuggestion('What are the latest updates on Tata Motors?')}>Tata Motors News</button>
                  <button className="suggestion-btn" onClick={() => applySuggestion('Show me the NIFTY 50 trend and recent news.')}>NIFTY 50 Analysis</button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="input-area absolute bottom-0 left-0 w-full z-10">
        {isProcessing && (
          <div className="processing-status" style={{ display: 'flex' }}>
            Pipeline thinking...
          </div>
        )}
        <div className="asset-toggle" aria-label="Asset type">
          {[
            { label: 'Auto', value: 'auto' },
            { label: 'Stocks', value: 'stock' },
            { label: 'Mutual Funds', value: 'mutual_fund' },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              className={assetType === option.value ? 'active' : ''}
              onClick={() => setAssetType(option.value as AssetType)}
              disabled={isProcessing}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={assetType === 'mutual_fund' ? 'Ask about mutual funds...' : assetType === 'stock' ? 'Ask about stocks, indices, or market news...' : 'Ask about stocks, mutual funds, indices, or market news...'}
            rows={1}
          />
          <button className="send-button" onClick={handleSend} aria-label="Send Message" disabled={isProcessing}>
            <Send size={20} />
          </button>
        </div>
      </div>
    </>
  );
}
