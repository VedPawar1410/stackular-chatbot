import ChatWidget from '@/components/ChatWidget';

export const metadata = {
  title: 'Stackular Chatbot (Demo) — built by Ved Pawar',
  description: 'Portfolio demo of a RAG website chatbot for Stackular. Not the official Stackular website.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body style={{ margin: 0, padding: 0, background: '#060b14' }}>
        {children}
        {/* Demo label: this is a portfolio demo, not the official Stackular site */}
        <div style={{
          position: 'fixed', bottom: 24, left: 24, zIndex: 9999,
          padding: '6px 12px', borderRadius: 999,
          background: 'rgba(250, 204, 21, 0.95)', color: '#111827',
          fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600,
          boxShadow: '0 4px 12px rgba(0,0,0,0.25)', maxWidth: 'calc(100vw - 110px)',
        }}>
          DEMO · Built by Ved Pawar · Not the official Stackular website
        </div>
        <ChatWidget />
      </body>
    </html>
  );
}