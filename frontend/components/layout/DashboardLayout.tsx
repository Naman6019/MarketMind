'use client';

import { useState, useEffect } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { useCanvasStore } from '@/store/useCanvasStore';
import { ChevronRight, ChevronLeft, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import ChatWindow from '@/components/chat/ChatWindow';
import StockDetailView from '@/components/canvas/StockDetailView';
import MFDetailView from '@/components/canvas/MFDetailView';
import ComparisonView from '@/components/canvas/ComparisonView';

export default function DashboardLayout() {
  const { isCanvasOpen, activeView, selectedIds, auxiliaryData, toggleCanvas } = useCanvasStore();
  const [isSidebarVisible, setIsSidebarVisible] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  // Wake up the backend on load
  useEffect(() => {
    fetch('/api/keepalive').catch(() => {});
  }, []);

  useEffect(() => {
    const query = window.matchMedia('(max-width: 768px)');
    const update = () => setIsMobile(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  const renderCanvasContent = () => {
    switch (activeView) {
      case 'STOCK_DETAIL':
        return <StockDetailView stockId={selectedIds[0]} />;
      case 'MF_DETAIL':
        return <MFDetailView schemeCode={selectedIds[0]} />;
      case 'COMPARISON':
        return <ComparisonView ids={selectedIds} type={selectedIds[0].match(/^[0-9]+$/) ? 'MUTUAL_FUND' : 'STOCK'} auxiliaryData={auxiliaryData} />;
      default:
        return <div className="p-6 text-gray-400">Select an item to view details.</div>;
    }
  };

  return (
    <div className={`app-container ${isSidebarVisible ? '' : 'sidebar-collapsed'}`}>
      <aside className={`sidebar ${isSidebarVisible ? '' : 'sidebar-hidden'} z-20 h-full flex flex-col`}>
        <div className="flex justify-between items-start mb-6">
          <div className="brand">
            <div className="logo"></div>
            <h1>MarketMind</h1>
          </div>
          <button 
            onClick={() => setIsSidebarVisible(false)}
            className="p-1.5 hover:bg-white/10 rounded-md text-gray-400 hover:text-white transition-colors"
            title="Hide Sidebar"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>
        <p className="tagline">Data-driven market context.</p>

        <div className="info-panel">
          <h3>Agent Pipeline</h3>
          <ul className="pipeline-list">
            <li><span className="dot q-dot"></span> Quant Agent</li>
            <li><span className="dot n-dot"></span> News Parser</li>
            <li><span className="dot s-dot"></span> Synthesis Core</li>
          </ul>
        </div>

        <div className="disclaimer-sidebar">
          <p>MarketMind is an informational research tool only. Nothing presented constitutes investment advice. Always consult a SEBI-registered Advisor.</p>
        </div>
      </aside>

      <main className="flex-1 h-full relative flex overflow-hidden gap-4">
        {isMobile ? (
          <div className="mobile-workspace">
            {isCanvasOpen ? (
              <>
                <button
                  onClick={toggleCanvas}
                  className="absolute top-3 right-3 z-50 bg-[#1f2833] border border-white/10 p-2 rounded-lg text-white hover:bg-white/10 transition-colors"
                  aria-label="Close comparison"
                >
                  <ChevronRight size={20} />
                </button>
                {renderCanvasContent()}
              </>
            ) : (
              <ChatWindow />
            )}
          </div>
        ) : (
        <PanelGroup direction="horizontal">
          <Panel defaultSize={isCanvasOpen ? 40 : 100} minSize={30} className="relative transition-all duration-300 ease-in-out chat-area">
            {!isSidebarVisible && (
              <button 
                onClick={() => setIsSidebarVisible(true)}
                className="absolute top-[72px] left-4 z-50 bg-[#1f2833] border border-white/10 p-2 rounded-lg text-white hover:bg-white/20 transition-all shadow-xl hover:scale-105"
                title="Show Sidebar"
              >
                <PanelLeftOpen size={20} />
              </button>
            )}
            <ChatWindow />
            
            <button 
              onClick={toggleCanvas}
              className="absolute top-4 right-4 z-50 bg-[#1f2833] border border-white/10 p-2 rounded-lg text-white hover:bg-white/10 transition-colors"
            >
              {isCanvasOpen ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
            </button>
          </Panel>

          {isCanvasOpen && (
            <>
              <PanelResizeHandle className="w-4 flex items-center justify-center cursor-col-resize user-select-none">
                <div className="w-1 h-8 bg-gray-600 rounded-full"></div>
              </PanelResizeHandle>
              <Panel defaultSize={60} minSize={40} className="animate-in slide-in-from-right-4 duration-300 ease-in-out">
                {renderCanvasContent()}
              </Panel>
            </>
          )}
        </PanelGroup>
        )}
      </main>
    </div>
  );
}
