import { create } from 'zustand'

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

interface AppState {
  // Global Progress
  progressPct: number
  progressMsg: string
  setProgress: (pct: number, msg: string) => void

  // Chatbot State
  isChatOpen: boolean
  setChatOpen: (open: boolean) => void
  chatHistory: ChatMessage[]
  addChatMessage: (msg: ChatMessage) => void
  updateLastMessage: (content: string | ((prev: string) => string)) => void
  clearChat: () => void

  // Review State
  activeReviewId: string | null
  setActiveReviewId: (id: string | null) => void
}

export const useStore = create<AppState>((set) => ({
  progressPct: 0,
  progressMsg: '',
  setProgress: (pct, msg) => set({ progressPct: pct, progressMsg: msg }),
  
  isChatOpen: false,
  setChatOpen: (open) => set({ isChatOpen: open }),
  chatHistory: [{ role: 'assistant', content: 'Ready. Ask me anything or type **yes** to approve.' }],
  addChatMessage: (msg) => set((state) => ({ chatHistory: [...state.chatHistory, msg] })),
  updateLastMessage: (content) => set((state) => {
    const history = [...state.chatHistory]
    if (history.length > 0) {
      const last = history[history.length - 1]
      last.content = typeof content === 'function' ? content(last.content) : content
    }
    return { chatHistory: history }
  }),
  clearChat: () => set({ chatHistory: [{ role: 'assistant', content: 'Ready.' }] }),
  
  activeReviewId: null,
  setActiveReviewId: (id) => set({ activeReviewId: id })
}))
