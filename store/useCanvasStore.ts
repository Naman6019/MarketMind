import { create } from 'zustand';

type ViewMode = 'NONE' | 'STOCK_DETAIL' | 'MF_DETAIL' | 'COMPARISON';

interface CanvasState {
  activeView: ViewMode;
  selectedIds: string[];
  isCanvasOpen: boolean;
  setView: (view: ViewMode) => void;
  setIds: (ids: string[]) => void;
  toggleCanvas: () => void;
  openCanvas: () => void;
  closeCanvas: () => void;
}

export const useCanvasStore = create<CanvasState>((set) => ({
  activeView: 'NONE',
  selectedIds: [],
  isCanvasOpen: false,
  setView: (view) => set({ activeView: view }),
  setIds: (ids) => set({ selectedIds: ids }),
  toggleCanvas: () => set((state) => ({ isCanvasOpen: !state.isCanvasOpen })),
  openCanvas: () => set({ isCanvasOpen: true }),
  closeCanvas: () => set({ isCanvasOpen: false }),
}));
