import { create } from 'zustand';

export type AssetType = 'auto' | 'stock' | 'mutual_fund';

export type Message = {
  id: string;
  role: 'user' | 'system';
  content: string;
};

const initialMessages: Message[] = [
  {
    id: '1',
    role: 'system',
    content: 'Welcome to MarketMind. I monitor NSE/BSE quant data and latest financial news. How can I assist your market research today?',
  },
];

interface ChatState {
  messages: Message[];
  input: string;
  isProcessing: boolean;
  assetType: AssetType;
  setInput: (input: string) => void;
  setIsProcessing: (isProcessing: boolean) => void;
  setAssetType: (assetType: AssetType) => void;
  addMessage: (message: Message) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: initialMessages,
  input: '',
  isProcessing: false,
  assetType: 'auto',
  setInput: (input) => set({ input }),
  setIsProcessing: (isProcessing) => set({ isProcessing }),
  setAssetType: (assetType) => set({ assetType }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
}));
