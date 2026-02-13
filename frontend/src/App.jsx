import { useState, useRef, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [isFileUploaded, setIsFileUploaded] = useState(false);
  const [isLoading, setIsLoading] = useState(false); 
  const [loadingStatus, setLoadingStatus] = useState(""); // Kullanıcıya ne yapıldığını göstermek için
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const [isBackendOnline, setIsBackendOnline] = useState(true);


  const clearHistory = () => {
  if (messages.length === 0) return; 
  
  if (window.confirm("Are you sure you want to clear the chat history?")) {
    // Sadece sohbet mesajlarını temizle, sistem mesajını (başarı mesajını) koru
    setMessages(prev => prev.filter(msg => msg.role === 'system')); 
  }
};
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleReset = () => {
    setIsFileUploaded(false);
  };

  const [darkMode, setDarkMode] = useState(() => {
    // İlk açılışta kullanıcının önceki tercihini kontrol et
    return localStorage.getItem('theme') === 'dark';
  });

  useEffect(() => {
    if (darkMode) {
      localStorage.setItem('theme', 'dark');
    } else {
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  const handleFileUpload = async (e) => {
    setIsLoading(true);

    const file = e.target.files[0];
    if (!file) return;

    if (file.type === "text/plain" || file.name.endsWith(".txt")) {
      alert("Invalid file format. Please select a PDF or DOCX file.");
      e.target.value = ""; 
      return;
    }

    // 1. Yükleme
    setLoadingStatus("Uploading and processing document..."); // Ekranda görünecek yazı

    const formData = new FormData();
    formData.append('file', file);

    try {
      // 2. Backend'e istek atılıyor
      await axios.post('http://localhost:8000/upload', formData);
      
      // 3. İşlem Başarılı
      setIsFileUploaded(true);
      
      // Eski mesajları koru (...prev) ve yeni sistem mesajını altına ekle
      setMessages(prev => [
        ...prev, 
        { 
          role: 'system', 
          content: `🔄 New document processed: "${file.name}". The AI is now answering based on this new file.` 
        }
      ]);
      
    } catch (error) {
      console.error("Upload error:", error);
      alert("An error occurred while processing the file.");
      // Hata olsa bile eski mesajları silme
    } finally {
      setIsLoading(false);
      setLoadingStatus("");
    }
  };

    const checkConnection = async () => {
      try {
        await axios.get('http://localhost:8000/health', { timeout: 5000 });
        setIsBackendOnline(true);
      } catch (error) {
        if (!isLoading) {
          setIsBackendOnline(false);
        }
      }
    };

    useEffect(() => {
    checkConnection(); // İlk açılışta kontrol et
    const interval = setInterval(checkConnection, 5000); // 5 saniyede bir tekrarla
    return () => clearInterval(interval); // Sayfa kapanınca durdur
  }, []);

  const handleSendMessage = async (e) => {
  e.preventDefault();
  if (!input.trim() || isLoading) return;

  const userMessage = input;
  setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
  setInput('');
  setIsLoading(true);

  try {
    const response = await axios.post('http://localhost:8000/ask', { 
      question: userMessage 
    });

    // --- Hata Ayıklama Bölümü ---
    console.log("Backend'den gelen ham veri:", response.data);

    let botReplyContent = "";

    if (response.data && response.data.answer) {
      botReplyContent = response.data.answer;
    } else if (typeof response.data === 'string') {
      botReplyContent = response.data;
    } else {
      botReplyContent = "DEBUG: Received data but no 'answer' key, data: " + JSON.stringify(response.data);
    }
    
    setMessages(prev => [...prev, { role: 'bot', content: botReplyContent }]);

  } catch (error) {
    console.error("Query Error:", error);
    const errorMsg = error.response?.data?.detail || "Network error or Server Timeout.";
    setMessages(prev => [...prev, { role: 'bot', content: `Error: ${errorMsg}` }]);
  } finally {
    setIsLoading(false);
  }
  
};

  return (
    <div className={`min-h-screen flex items-center justify-center p-4 transition-colors duration-500 ${
      darkMode ? 'bg-zinc-950' : 'bg-gray-100'
    }`}>
      <div className={`w-full max-w-4xl rounded-2xl shadow-2xl flex flex-col h-[85vh] overflow-hidden transition-colors duration-500 ${
        darkMode ? 'bg-zinc-900 border border-zinc-800' : 'bg-white'
      }`}>
        
        
        {/* Header */}
        <div className={`p-4 text-white flex justify-between items-center transition-colors duration-500 ${
          darkMode ? 'bg-zinc-900 border-b border-zinc-800' : 'bg-slate-800'
        }`}>
          
          {/* Sol Kısım: Işık ve Başlık */}
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full transition-all duration-500 ${
              isBackendOnline 
                ? 'bg-green-400 animate-pulse shadow-[0_0_10px_rgba(74,222,128,0.5)]' 
                : 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]'
            }`}></div>
            <h1 className="font-bold text-lg hidden sm:block">
              {isBackendOnline ? 'FILE TEACHER' : 'Connection Lost...'}
            </h1>
          </div>

          {/* Sağ Kısım: Aksiyon Butonları */}
          <div className="flex items-center gap-2">
            
            {/* 1. TEMA DEĞİŞTİRME BUTONU */}
            <button 
              onClick={() => setDarkMode(!darkMode)}
              className={`p-2 rounded-lg transition-colors ${
                darkMode ? 'bg-zinc-800 text-yellow-400 hover:bg-zinc-700' : 'bg-slate-700 text-blue-300 hover:bg-slate-600'
              }`}
              title="Toggle Theme"
            >
              {darkMode ? '☀️' : '🌙'}
            </button>

            {isFileUploaded && (
              <>
                {/* 2. CLEAR CHAT BUTONU (HESABA KATILDI) */}
                <button 
                  onClick={clearHistory}
                  disabled={isLoading}
                  className={`text-xs py-2 px-3 rounded-lg font-medium transition-all flex items-center gap-1 ${
                    darkMode 
                      ? 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600 border border-zinc-600' 
                      : 'bg-slate-700 text-slate-200 hover:bg-slate-600'
                  } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                  Clear chat
                </button>

                {/* 3. NEW FILE BUTONU */}
                <button 
                  onClick={handleReset}
                  className={`text-xs py-2 px-3 rounded-lg font-medium transition-all ${
                    darkMode 
                      ? 'bg-red-900/80 text-red-200 hover:bg-red-800 border border-red-700' 
                      : 'bg-red-500 hover:bg-red-600 text-white'
                  }`}
                >
                  New File
                </button>
              </>
            )}
          </div>
        </div>
{!isFileUploaded ? (
  /* --- UPLOAD SCREEN --- */
  <div className={`flex-1 flex flex-col items-center justify-center p-10 transition-colors duration-500 relative ${
    (darkMode && isLoading) ? 'bg-zinc-900' : (darkMode ? 'bg-zinc-800' : 'bg-gray-50')
  }`}>
    
    {/* Eğer yükleniyorsa SPINNER göster, yoksa FORM göster */}
    {isLoading ? (
      /* --- PROCESSING STATE --- */
      <div className="flex flex-col items-center justify-center text-center">
        <div className="relative w-24 h-24 mx-auto mb-6">
          {/* Dış Halka */}
          <div className={`absolute inset-0 border-4 rounded-full ${darkMode ? 'border-zinc-700' : 'border-gray-200'}`}></div>
          {/* Dönen Halka */}
          <div className="absolute inset-0 border-4 border-blue-500 rounded-full border-t-transparent animate-spin"></div>
          {/* İkon */}
          <div className="absolute inset-0 flex items-center justify-center">
            <svg className="w-8 h-8 text-blue-500 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
            </svg>
          </div>
        </div>
        <h3 className={`text-xl font-bold mb-2 ${darkMode ? 'text-zinc-100' : 'text-gray-700'}`}>Processing Document</h3>
        <p className="text-blue-500 font-medium animate-pulse">{loadingStatus}</p>
        <p className={`text-sm mt-4 max-w-xs mx-auto ${darkMode ? 'text-zinc-400' : 'text-gray-400'}`}>
          Creating embeddings and vector chunks...
        </p>
      </div>
    ) : (
      /* --- SELECTION STATE --- */
      <>
        <div className="mb-8 text-center">
          <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 shadow-sm ${darkMode ? 'bg-zinc-700' : 'bg-blue-100'}`}>
            <svg className={`w-8 h-8 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
          </div>
          <h2 className={`text-2xl font-bold ${darkMode ? 'text-zinc-100' : 'text-gray-800'}`}>
            Document Analysis
          </h2>
          <p className={darkMode ? 'text-zinc-400' : 'text-gray-500'}>Upload a document (PDF/DOCX) to start.</p>
        </div>

        <label className={`group w-full max-w-md flex flex-col items-center px-4 py-8 rounded-xl cursor-pointer transition-all duration-300 shadow-sm hover:shadow-md border-2 border-dashed ${
          darkMode 
            ? 'bg-zinc-800 border-zinc-700 hover:bg-zinc-700 hover:border-zinc-500' 
            : 'bg-white border-blue-300 hover:bg-blue-50 hover:border-blue-500'
        }`}>
          <svg className={`w-10 h-10 mb-3 transition-colors ${darkMode ? 'text-zinc-400' : 'text-blue-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <span className={`font-medium group-hover:scale-105 transition-transform ${darkMode ? 'text-zinc-200' : 'text-blue-600'}`}>
            Select a File
          </span>
          <input type='file' className="hidden" onChange={handleFileUpload} accept=".pdf,.docx,.doc" />
        </label>
      </>
    )}
  </div>
) : (
          /* --- CHAT SCREEN --- */
          <div className="flex-1 flex flex-col overflow-hidden relative">
            <div className={`flex-1 overflow-y-auto p-4 space-y-4 dark-scrollbar transition-all duration-700 ${
                isLoading && !isFileUploaded
                  ? 'bg-black opacity-90' 
                  : (darkMode ? 'bg-zinc-900' : 'bg-white')
              }`}>
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] p-4 rounded-2xl text-sm leading-relaxed ${
                    msg.role === 'user' 
                      ? 'bg-blue-600 text-white' 
                      : darkMode 
                        ? 'bg-zinc-800 text-zinc-200 border border-zinc-700' // Dark Bot
                        : 'bg-gray-100 text-gray-800 border border-gray-200' // Light Bot
                  }`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {/* Chat içi yükleniyor animasyonu */}
              {isLoading && (
                 <div className="flex justify-start">
                    <div className="bg-gray-100 p-4 rounded-2xl rounded-bl-none border border-gray-200 flex space-x-2 items-center">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                 </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <form 
              onSubmit={handleSendMessage} 
              className={`p-4 border-t transition-colors duration-500 flex gap-3 ${
                darkMode 
                  ? 'bg-zinc-900 border-zinc-800' 
                  : 'bg-gray-50 border-gray-200'
              }`}
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question..."
                className={`flex-1 p-3 rounded-xl outline-none transition-all duration-300 ${
                  darkMode 
                    ? 'bg-zinc-800 border-zinc-700 text-zinc-100 placeholder-zinc-500 focus:ring-2 focus:ring-blue-600' 
                    : 'bg-white border-gray-300 text-gray-900 focus:ring-2 focus:ring-blue-500 shadow-sm'
                }`}
                disabled={isLoading}
              />
              <button 
                type="submit" 
                disabled={isLoading || !input.trim()}
                className={`px-6 py-3 rounded-xl font-medium transition-all active:scale-95 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed ${
                  darkMode
                    ? 'bg-blue-700 hover:bg-blue-600 text-white'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  'Send'
                )}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;