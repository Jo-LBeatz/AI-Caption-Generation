import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Upload, FileVideo, CheckCircle2, Download, PlayCircle, Loader2, LogOut } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { AnimatedDownload } from '@/components/ui/animated-download';
import { AuthPage } from '@/components/auth/AuthPage';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface JobStatus {
  status: 'processing' | 'extracting_audio' | 'transcribing' | 'checking_faith_alignment' | 'embedding_captions' | 'completed' | 'failed';
  progress: number;
  filename: string;
  video_burned?: boolean;
  error?: string;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [srtContent, setSrtContent] = useState<string>('');
  const [embedCaptions, setEmbedCaptions] = useState(false);

  // Auth State
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [userEmail, setUserEmail] = useState<string | null>(localStorage.getItem('user_email'));

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAuthSuccess = (newToken: string, email: string) => {
    localStorage.setItem('token', newToken);
    localStorage.setItem('user_email', email);
    setToken(newToken);
    setUserEmail(email);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user_email');
    setToken(null);
    setUserEmail(null);
    reset();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] || null);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  // Poll status when jobId exists
  useEffect(() => {
    let interval: any;
    if (jobId && token && (!status || (status.status !== 'completed' && status.status !== 'failed'))) {
      interval = setInterval(async () => {
        try {
          const response = await axios.get<JobStatus>(`${API_BASE_URL}/status/${jobId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          setStatus(response.data);

          if (response.data.status === 'completed') {
            clearInterval(interval);
            // Fetch SRT content for preview
            try {
              const srtResponse = await axios.get<{ content: string }>(`${API_BASE_URL}/srt/${jobId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
              });
              setSrtContent(srtResponse.data.content);
            } catch (e) {
              console.error("SRT fetch error", e);
            }
          } else if (response.data.status === 'failed') {
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Error fetching status:', error);
          if ((error as any).response?.status === 401) {
            logout();
          }
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [jobId, status, token]);

  const handleUpload = async () => {
    if (!file || !token) return;

    setIsUploading(true);
    setSrtContent('');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_BASE_URL}/upload?embed_captions=${embedCaptions}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${token}`
        },
      });
      setJobId(response.data.job_id);
    } catch (error) {
      console.error('Upload error:', error);
      if ((error as any).response?.status === 401) {
        logout();
      } else {
        alert('Failed to upload video. Please try again.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setJobId(null);
    setStatus(null);
    setSrtContent('');
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-12 md:px-8 bg-[#050504]">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-4xl relative"
      >
        {/* Header Section */}
        <div className="text-center mb-10">
          <motion.h1
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            className="text-4xl md:text-5xl font-black title-gradient mb-3 tracking-tighter"
          >
            Captions by Jo-L
          </motion.h1>
          <p className="text-stone-400 text-sm md:text-base font-medium">
            What is the good, the true and the beautiful video that you want to get captions for?
          </p>
        </div>

        {/* Main Content Area */}
        <AnimatePresence mode="wait">
          {!token ? (
            <AuthPage key="auth" apiBaseUrl={API_BASE_URL} onAuthSuccess={handleAuthSuccess} />
          ) : !jobId ? (
            <motion.div
              key="upload"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-stone-900/40 backdrop-blur-xl border border-white/5 rounded-3xl p-8 md:p-12 shadow-2xl"
            >
              <div className="flex flex-col items-center justify-center space-y-8">
                <div
                  className={`w-full aspect-video md:aspect-[21/9] border-2 border-dashed rounded-3xl flex flex-col items-center justify-center transition-all cursor-pointer group ${file ? 'border-amber-500/50 bg-amber-500/5' : 'border-white/10 hover:border-white/20 hover:bg-white/[0.02]'
                    }`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    accept="video/*"
                    className="hidden"
                  />
                  {file ? (
                    <>
                      <div className="w-16 h-16 bg-amber-500/20 rounded-full flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                        <FileVideo className="text-amber-500" size={32} />
                      </div>
                      <p className="text-white font-bold text-lg px-6 truncate max-w-full italic">
                        "{file.name}"
                      </p>
                      <p className="text-stone-500 text-sm mt-1">
                        {(file.size / (1024 * 1024)).toFixed(1)} MB • Click to change
                      </p>
                    </>
                  ) : (
                    <>
                      <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                        <Upload className="text-stone-400 group-hover:text-amber-500 transition-colors" size={32} />
                      </div>
                      <h3 className="text-white font-black text-xl tracking-tight">Drop your masterpiece here</h3>
                      <p className="text-stone-500 text-sm mt-1">MP4, MOV, or MKV (up to 2h)</p>
                    </>
                  )}
                </div>

                <div className="flex items-center gap-2 px-2 cursor-pointer group" onClick={() => setEmbedCaptions(!embedCaptions)}>
                  <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${embedCaptions ? 'bg-amber-600 border-amber-600' : 'border-white/20 group-hover:border-amber-500/50'}`}>
                    {embedCaptions && <CheckCircle2 size={12} className="text-black" />}
                  </div>
                  <span className="text-sm font-bold text-stone-300 select-none">Burn captions into video (Ready to Share)</span>
                </div>

                <Button
                  onClick={handleUpload}
                  disabled={!file || isUploading}
                  className="w-full h-16 bg-white hover:bg-amber-500 text-black font-black text-xl rounded-2xl shadow-lg transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-30 disabled:hover:scale-100"
                >
                  {isUploading ? (
                    <><Loader2 className="animate-spin mr-3" size={24} /> Starting engine...</>
                  ) : (
                    <>+ Generate Captions</>
                  )}
                </Button>

                <button
                  onClick={logout}
                  className="text-stone-600 hover:text-stone-400 text-xs font-bold uppercase tracking-widest transition-colors flex items-center gap-2"
                >
                  <LogOut size={12} /> Sign out of {userEmail}
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="processing"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-stone-900/40 backdrop-blur-xl border border-white/5 rounded-3xl p-8 md:p-12 shadow-2xl"
            >
              {status?.status !== 'completed' && status?.status !== 'failed' ? (
                <div className="flex flex-col items-center space-y-12 py-6 text-center">
                  <AnimatedDownload
                    progress={status?.progress || 0}
                    label={status?.status?.replace('_', ' ').toUpperCase() || 'INITIALIZING'}
                    className="mx-auto"
                    isAnimating={true}
                    timeRemaining={
                      status?.progress && status.progress > 0 ?
                        `${Math.floor(((100 - status.progress) * 1.5) / 60)}min ${Math.floor(((100 - status.progress) * 1.5) % 60).toString().padStart(2, '0')}sec` :
                        "Calculating..."
                    }
                  />

                  <div className="space-y-3">
                    <h3 className="font-black text-white text-3xl tracking-tighter">
                      {status?.status === 'transcribing' ? 'Transcribing Your Story...' :
                        status?.status === 'checking_faith_alignment' ? 'Finalizing Quality Alignment...' :
                          status?.status === 'embedding_captions' ? 'Polishing the Movie...' :
                            'Ignition in Progress...'}
                    </h3>
                    <p className="text-stone-500 text-sm font-medium">Please keep this window open while the engines hum.</p>
                  </div>
                </div>
              ) : status?.status === 'completed' ? (
                <div className="flex flex-col md:flex-row gap-8 items-start">
                  <div className="flex-1 space-y-6 w-full">
                    <div className="flex items-center gap-4 p-6 bg-amber-500/10 border border-amber-500/20 rounded-3xl">
                      <div className="w-12 h-12 bg-amber-500/20 rounded-full flex items-center justify-center">
                        <CheckCircle2 className="text-amber-500" size={28} />
                      </div>
                      <div>
                        <h3 className="font-black text-white text-xl tracking-tight">Your Captions are Ready</h3>
                        <p className="text-amber-500/60 text-sm font-bold uppercase tracking-widest">SUCCESSFUL COMPLETION</p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <a href={`${API_BASE_URL}/download/${jobId}?authorization=Bearer ${token}`} download className="block">
                        <Button className="w-full h-12 text-base font-bold rounded-2xl bg-stone-800 hover:bg-stone-700 text-slate-200">
                          <Download className="mr-2" size={18} /> Get .SRT File
                        </Button>
                      </a>

                      {status?.video_burned && (
                        <a href={`${API_BASE_URL}/download-video/${jobId}?authorization=Bearer ${token}`} download className="block">
                          <Button className="w-full h-16 text-xl font-black rounded-2xl bg-gradient-to-r from-amber-600 to-amber-700 hover:opacity-90 shadow-xl shadow-amber-900/20">
                            <PlayCircle className="mr-2" size={24} /> Download Final Video
                          </Button>
                        </a>
                      )}

                      <Button variant="ghost" onClick={reset} className="w-full text-stone-500 hover:text-white uppercase text-xs font-black tracking-widest">
                        Process Another Masterpiece
                      </Button>

                      <button onClick={logout} className="w-full mt-4 text-stone-600 hover:text-stone-400 text-[10px] font-black uppercase tracking-[0.2em] flex items-center justify-center gap-2">
                        <LogOut size={10} /> Logout
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 w-full h-[400px] bg-black/40 border border-white/5 rounded-3xl overflow-hidden hidden md:block">
                    <div className="p-4 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                      <span className="text-xs font-black text-stone-500 uppercase tracking-widest">SRT Preview</span>
                      <span className="text-[10px] text-stone-600">utf-8 encoding</span>
                    </div>
                    <textarea
                      readOnly
                      value={srtContent}
                      className="w-full h-full bg-transparent p-6 text-stone-400 font-mono text-[10px] resize-none focus:outline-none scrollbar-hide"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-center py-10 space-y-6">
                  <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/20">
                    <span className="text-4xl text-red-500 font-black">!</span>
                  </div>
                  <div className="space-y-4">
                    <h3 className="font-black text-white text-3xl tracking-tighter">Process Stopped</h3>
                    <p className="text-red-400/80 font-bold max-w-sm mx-auto p-4 bg-red-500/5 rounded-2xl border border-red-500/10 whitespace-pre-wrap">
                      {status?.error || "An unexpected error occurred during processing."}
                    </p>
                  </div>
                  <Button onClick={reset} className="px-8 h-12 bg-white text-black font-black uppercase tracking-tighter rounded-full hover:bg-stone-200">
                    Try Again
                  </Button>
                  <button onClick={logout} className="block mx-auto mt-4 text-stone-600 hover:text-stone-400 text-[10px] font-black uppercase tracking-[0.2em] flex items-center justify-center gap-2">
                    <LogOut size={10} /> Sign out
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Footer Details */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-10 flex flex-wrap justify-center gap-6 text-stone-500 text-[10px] font-black uppercase tracking-[0.2em]"
        >
          <span className="flex items-center gap-1.5"><CheckCircle2 size={12} className="text-amber-500/50" /> Professional Standard</span>
          <span className="flex items-center gap-1.5"><CheckCircle2 size={12} className="text-amber-500/50" /> Pro-Grade SRT</span>
          <span className="flex items-center gap-1.5"><CheckCircle2 size={12} className="text-amber-500/50" /> Privacy Focused</span>
        </motion.div>
      </motion.div>
    </div>
  );
}
