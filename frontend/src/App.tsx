import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Upload,
  FileVideo,
  CheckCircle2,
  Download,
  PlayCircle,
  Loader2,
  AlertTriangle,
  Volume2,
  VolumeX,
  Clock,
  Smartphone,
  ShieldAlert,
  Flame,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { AnimatedDownload } from '@/components/ui/animated-download';
import { LanguageAccentDialog } from '@/components/LanguageAccentDialog';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

interface TopCandidate {
  language: string;
  probability: number;
}

interface MoralityAlert {
  is_evil: boolean;
  title: string;
  commandment_violated: string;
  reason: string;
  scriptural_basis: string;
}

interface JobStatus {
  status:
    | 'processing'
    | 'extracting_audio'
    | 'detecting_language'
    | 'awaiting_user_confirmation'
    | 'transcribing'
    | 'generating_srt'
    | 'checking_morality'
    | 'morality_warning'
    | 'embedding_captions'
    | 'completed'
    | 'failed';
  progress: number;
  eta_seconds?: number;
  duration?: number;
  filename: string;
  video_burned?: boolean;
  has_srt?: boolean;
  morality_alert?: MoralityAlert;
  error?: string;
  detected_language?: string;
  detected_probability?: number;
  detected_top_candidates?: TopCandidate[];
  final_language?: string;
}

// ---------------------------------------------------------------------------
// High-Urgency Audio Alarm Synthesizer (Web Audio API & Vibration)
// Works reliably across mobile phone browsers (iOS/Android) and desktop.
// ---------------------------------------------------------------------------
class AlarmSounder {
  private ctx: AudioContext | null = null;
  private isPlaying = false;
  private intervalId: any = null;

  start() {
    if (this.isPlaying) return;
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      this.ctx = new AudioCtx();
      this.isPlaying = true;

      let highTone = true;
      const playPulse = () => {
        if (!this.ctx || !this.isPlaying) return;
        try {
          if (this.ctx.state === 'suspended') {
            this.ctx.resume();
          }
          const osc = this.ctx.createOscillator();
          const gain = this.ctx.createGain();

          osc.type = 'sawtooth';
          // Urgent alternating European siren frequencies (960Hz and 770Hz)
          osc.frequency.setValueAtTime(highTone ? 960 : 770, this.ctx.currentTime);
          highTone = !highTone;

          gain.gain.setValueAtTime(0.3, this.ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.35);

          osc.connect(gain);
          gain.connect(this.ctx.destination);

          osc.start();
          osc.stop(this.ctx.currentTime + 0.35);

          // Vibrate mobile phone if supported
          if (typeof navigator !== 'undefined' && navigator.vibrate) {
            navigator.vibrate([250, 100, 250]);
          }
        } catch (e) {
          console.error('Alarm pulse error:', e);
        }
      };

      playPulse();
      this.intervalId = setInterval(playPulse, 400);
    } catch (e) {
      console.error('AudioContext start error:', e);
    }
  }

  stop() {
    this.isPlaying = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    if (this.ctx) {
      try {
        this.ctx.close();
      } catch (e) {}
      this.ctx = null;
    }
  }
}

const alarmSounder = new AlarmSounder();

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    processing: 'Initializing...',
    extracting_audio: 'Extracting Audio Track...',
    detecting_language: 'Detecting Language & Dialect...',
    awaiting_user_confirmation: 'Awaiting Language Confirmation',
    transcribing: 'Transcribing with large-v3-turbo...',
    generating_srt: 'Generating Subtitles (.SRT)...',
    checking_morality: 'Theological Conscience Check...',
    morality_warning: 'Moral Law Warning Triggered',
    embedding_captions: 'Burning Subtitles into Video...',
    completed: 'Complete',
    failed: 'Halted',
  };
  return labels[status] || status.replace(/_/g, ' ').toUpperCase();
}

function formatCountdown(secs: number | null): string {
  if (secs === null || secs <= 0) return 'Calculating...';
  const hours = Math.floor(secs / 3600);
  const minutes = Math.floor((secs % 3600) / 60);
  const remainingSecs = secs % 60;
  if (hours > 0) {
    return `${hours}h ${minutes.toString().padStart(2, '0')}m ${remainingSecs.toString().padStart(2, '0')}s`;
  }
  return `${minutes}min ${remainingSecs.toString().padStart(2, '0')}sec`;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [countdownSecs, setCountdownSecs] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [srtContent, setSrtContent] = useState<string>('');
  const [embedCaptions, setEmbedCaptions] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [alarmMuted, setAlarmMuted] = useState(false);
  const [serverIp, setServerIp] = useState<string>('');
  const [showPhoneInfo, setShowPhoneInfo] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch server info (LAN IP) on load
  useEffect(() => {
    axios
      .get(`${API_BASE_URL}/server-info`)
      .then((res) => {
        if (res.data?.local_ip) {
          setServerIp(res.data.local_ip);
        }
      })
      .catch(() => {});
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] || null);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  // Real-time 1-second countdown ticking timer
  const isAwaitingConfirmation = status?.status === 'awaiting_user_confirmation';
  const isProcessing =
    !!jobId &&
    !isAwaitingConfirmation &&
    status?.status !== 'completed' &&
    status?.status !== 'failed' &&
    status?.status !== 'morality_warning';

  useEffect(() => {
    if (!isProcessing) return;
    const timer = setInterval(() => {
      setCountdownSecs((prev) => {
        if (prev === null || prev <= 0) return 0;
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [isProcessing]);

  // Status Polling Effect
  useEffect(() => {
    let interval: any;
    let isMounted = true;
    const terminalStatuses = ['completed', 'failed', 'awaiting_user_confirmation', 'morality_warning'];

    if (jobId && (!status || !terminalStatuses.includes(status.status))) {
      const fetchStatus = async () => {
        try {
          const response = await axios.get<JobStatus>(`${API_BASE_URL}/status/${jobId}`);
          if (!isMounted) return;
          setStatus(response.data);

          if (response.data.eta_seconds !== undefined && response.data.eta_seconds > 0) {
            setCountdownSecs(response.data.eta_seconds);
          }

          if (response.data.status === 'morality_warning') {
            // Trigger emergency audio alarm
            if (!alarmMuted) {
              alarmSounder.start();
            }
          }

          if (response.data.status === 'completed') {
            setCountdownSecs(0);
          }

          if (
            response.data.status === 'completed' ||
            response.data.status === 'embedding_captions' ||
            response.data.progress >= 73
          ) {
            try {
              const srtResponse = await axios.get<{ content: string }>(`${API_BASE_URL}/srt/${jobId}`);
              if (isMounted) setSrtContent(srtResponse.data.content);
            } catch (e) {
              // SRT in progress
            }
          }
        } catch (error) {
          console.error('Error fetching status:', error);
        }
      };

      // Poll immediately without waiting for interval
      fetchStatus();
      interval = setInterval(fetchStatus, 1000);
    }

    return () => {
      isMounted = false;
      if (interval) clearInterval(interval);
    };
  }, [jobId, status?.status, alarmMuted]);

  // Clean up alarm sound when unmounting or leaving warning state
  useEffect(() => {
    if (status?.status !== 'morality_warning') {
      alarmSounder.stop();
    }
  }, [status?.status]);

  const toggleAlarm = () => {
    if (alarmMuted) {
      setAlarmMuted(false);
      alarmSounder.start();
    } else {
      setAlarmMuted(true);
      alarmSounder.stop();
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setSrtContent('');
    setCountdownSecs(null);
    setAlarmMuted(false);
    alarmSounder.stop();

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/upload?embed_captions=${embedCaptions}`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
        }
      );
      const newJobId = response.data.job_id;
      setJobId(newJobId);
      setStatus({
        status: response.data.status || 'extracting_audio',
        progress: response.data.progress || 5,
        eta_seconds: response.data.eta_seconds || 15,
        filename: file.name,
        video_burned: false,
        has_srt: false,
      });
      setCountdownSecs(response.data.eta_seconds || 15);
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload video. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleLanguageConfirm = async (language: string, accentId: string) => {
    if (!jobId) return;
    setIsConfirming(true);
    try {
      await axios.post(`${API_BASE_URL}/confirm-language/${jobId}`, {
        language,
        accent_id: accentId,
      });
      setStatus((prev) => (prev ? { ...prev, status: 'transcribing', progress: 25 } : prev));
    } catch (error) {
      console.error('Language confirm error:', error);
      alert('Failed to confirm language. Please try again.');
    } finally {
      setIsConfirming(false);
    }
  };

  const handleProceedDespiteWarning = async () => {
    if (!jobId) return;
    alarmSounder.stop();
    try {
      await axios.post(`${API_BASE_URL}/proceed-despite-warning/${jobId}`);
      setStatus((prev) => (prev ? { ...prev, status: 'embedding_captions', progress: 78 } : prev));
    } catch (error) {
      console.error('Proceed error:', error);
      alert('Failed to resume processing.');
    }
  };

  const handleCancelAfterWarning = async () => {
    if (!jobId) return;
    alarmSounder.stop();
    try {
      await axios.post(`${API_BASE_URL}/cancel-job/${jobId}`);
      reset();
    } catch (error) {
      console.error('Cancel error:', error);
      reset();
    }
  };

  const handleDownloadSrt = async () => {
    if (!jobId) return;

    const pyApi = (window as any).pywebview?.api;
    if (pyApi?.save_srt) {
      try {
        const suggestedName = status?.filename
          ? status.filename.replace(/\.[^/.]+$/, '') + '.srt'
          : `captions_${jobId.slice(0, 8)}.srt`;
        const result = await pyApi.save_srt(jobId, suggestedName);
        if (result?.error && result.error !== 'cancelled') {
          alert(`Could not save SRT file: ${result.error}`);
        }
      } catch (e) {
        console.error('pywebview save_srt error', e);
        alert('Failed to save SRT file via native dialog.');
      }
      return;
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/download/${jobId}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${status?.filename ? status.filename.replace(/\.[^/.]+$/, '') : 'captions'}.srt`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Download SRT error', e);
      alert('Failed to download SRT file.');
    }
  };

  const handleDownloadVideo = async () => {
    if (!jobId) return;

    const pyApi = (window as any).pywebview?.api;
    if (pyApi?.save_video) {
      try {
        const baseName = status?.filename ? status.filename.replace(/\.[^/.]+$/, '') : 'video';
        const suggestedName = `${baseName}_captioned.mp4`;
        const result = await pyApi.save_video(jobId, suggestedName);
        if (result?.error && result.error !== 'cancelled') {
          alert(`Could not save video: ${result.error}`);
        }
      } catch (e) {
        console.error('pywebview save_video error', e);
        alert('Failed to save video via native dialog.');
      }
      return;
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/download-video/${jobId}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute(
        'download',
        `${status?.filename ? status.filename.replace(/\.[^/.]+$/, '') : 'video'}_captioned.mp4`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Download video error', e);
      alert('Failed to download video file.');
    }
  };

  // Download both .mp4 and .srt together
  const handleDownloadBoth = async () => {
    await handleDownloadVideo();
    setTimeout(() => {
      handleDownloadSrt();
    }, 800);
  };

  const reset = () => {
    alarmSounder.stop();
    setFile(null);
    setJobId(null);
    setStatus(null);
    setCountdownSecs(null);
    setSrtContent('');
    setIsConfirming(false);
    setAlarmMuted(false);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-12 md:px-8 bg-[#070605] text-stone-100 selection:bg-amber-500/30">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-4xl relative">
        {/* Header Section */}
        <div className="text-center mb-8 flex flex-col items-center">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="relative mb-3 group"
          >
            <div className="absolute -inset-1.5 bg-gradient-to-r from-amber-600 to-yellow-500 rounded-3xl blur-md opacity-40 group-hover:opacity-70 transition duration-500" />
            <img
              src="/logo.png"
              alt="Verbum Sacred AI Emblem"
              className="relative w-24 h-24 md:w-28 md:h-28 rounded-2xl border border-amber-500/40 object-cover shadow-2xl bg-black"
            />
          </motion.div>

          <motion.h1
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            className="text-4xl md:text-6xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-b from-amber-200 via-amber-400 to-yellow-600 mb-1"
          >
            VERBUM
          </motion.h1>

          <p className="text-amber-500/80 text-xs md:text-sm font-serif italic tracking-wide mb-1">
            "In principio erat Verbum" — John 1:1
          </p>
          <p className="text-stone-400 text-sm md:text-base font-medium max-w-lg">
            Sacred clarity, high-precision multilingual speech-to-text, and video caption generation.
          </p>

          {/* Mobile Connect Pill */}
          {serverIp && (
            <button
              onClick={() => setShowPhoneInfo(!showPhoneInfo)}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-stone-900 border border-stone-800 text-[11px] font-semibold text-stone-400 hover:text-amber-400 transition-colors"
            >
              <Smartphone size={13} className="text-amber-500" />
              <span>Mobile Phone Access: http://{serverIp}:8000</span>
            </button>
          )}

          {showPhoneInfo && (
            <div className="mt-2 p-3 bg-stone-900/90 border border-amber-500/30 rounded-2xl text-xs text-stone-300 max-w-sm">
              <p>Connect your phone to the same Wi-Fi network and open:</p>
              <p className="font-mono text-amber-400 mt-1 select-all font-bold">http://{serverIp}:8000</p>
              <p className="text-[10px] text-stone-500 mt-1">
                You will receive real-time progress and the loud alarm will sound directly through your phone!
              </p>
            </div>
          )}
        </div>

        {/* Main Content Area */}
        <AnimatePresence mode="wait">
          {/* ── 1. Upload Screen ── */}
          {!jobId ? (
            <motion.div
              key="upload"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-stone-950/80 backdrop-blur-xl border border-amber-500/20 rounded-3xl p-8 md:p-12 shadow-2xl"
            >
              <div className="flex flex-col items-center justify-center space-y-8">
                <div
                  className={`w-full aspect-video md:aspect-[21/9] border-2 border-dashed rounded-3xl flex flex-col items-center justify-center transition-all cursor-pointer group ${
                    file
                      ? 'border-amber-500/70 bg-amber-500/5'
                      : 'border-stone-800 hover:border-amber-500/40 hover:bg-white/[0.02]'
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
                        <FileVideo className="text-amber-400" size={32} />
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
                      <div className="w-16 h-16 bg-stone-900 rounded-full flex items-center justify-center mb-4 group-hover:scale-110 transition-transform border border-stone-800">
                        <Upload className="text-stone-400 group-hover:text-amber-400 transition-colors" size={30} />
                      </div>
                      <h3 className="text-white font-bold text-xl tracking-tight">Drop your video here</h3>
                      <p className="text-stone-500 text-sm mt-1">MP4, MOV, MKV, AVI, WebM — any language or dialect</p>
                    </>
                  )}
                </div>

                <div
                  className="flex items-center gap-2.5 px-3 py-1 cursor-pointer group"
                  onClick={() => setEmbedCaptions(!embedCaptions)}
                >
                  <div
                    className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${
                      embedCaptions
                        ? 'bg-amber-600 border-amber-600'
                        : 'border-stone-700 group-hover:border-amber-500/50'
                    }`}
                  >
                    {embedCaptions && <CheckCircle2 size={13} className="text-black stroke-[3]" />}
                  </div>
                  <span className="text-sm font-semibold text-stone-300 select-none">
                    Burn captions into video (Produces both burnt-in video + .SRT file)
                  </span>
                </div>

                <Button
                  onClick={handleUpload}
                  disabled={!file || isUploading}
                  className="w-full h-16 bg-gradient-to-r from-amber-500 to-yellow-600 hover:from-amber-600 hover:to-yellow-700 text-black font-black text-xl rounded-2xl shadow-xl shadow-amber-950/30 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-30 disabled:hover:scale-100"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="animate-spin mr-3" size={24} />
                      Uploading &amp; Analyzing...
                    </>
                  ) : (
                    <>✦ Generate Captions</>
                  )}
                </Button>
              </div>
            </motion.div>

          /* ── 2. Language & Accent Confirmation Screen ── */
          ) : isAwaitingConfirmation ? (
            <motion.div
              key="lang-confirm"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-stone-950/80 backdrop-blur-xl border border-amber-500/20 rounded-3xl p-8 md:p-10 shadow-2xl"
            >
              <LanguageAccentDialog
                detectedLanguage={status?.detected_language || 'en'}
                detectedProbability={status?.detected_probability || 0}
                topCandidates={status?.detected_top_candidates || []}
                onConfirm={handleLanguageConfirm}
                isConfirming={isConfirming}
              />
            </motion.div>

          /* ── 3. Morality Warning Screen (DANGER! EVIL MESSAGE DETECTED) ── */
          ) : status?.status === 'morality_warning' ? (
            <motion.div
              key="morality-warning"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-gradient-to-b from-stone-950 to-red-950/70 border-2 border-red-600/80 rounded-3xl p-6 md:p-10 shadow-[0_0_60px_rgba(220,38,38,0.4)] relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-4 flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={toggleAlarm}
                  className="bg-black/60 border-red-500/40 text-red-300 hover:text-white hover:bg-red-950 text-xs"
                >
                  {alarmMuted ? (
                    <>
                      <VolumeX size={14} className="mr-1.5" /> Alarm Muted
                    </>
                  ) : (
                    <>
                      <Volume2 size={14} className="mr-1.5 text-red-400 animate-pulse" /> Siren Sounding (Mute)
                    </>
                  )}
                </Button>
              </div>

              <div className="flex flex-col items-center text-center space-y-6">
                <div className="w-20 h-20 bg-red-600/20 rounded-full flex items-center justify-center border-2 border-red-500 animate-bounce">
                  <ShieldAlert className="text-red-500" size={44} />
                </div>

                <div className="space-y-2 max-w-2xl">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-950/80 border border-red-600/60 text-red-400 font-bold text-xs uppercase tracking-widest">
                    <Flame size={14} /> Moral Law Violation Detected
                  </span>

                  <h2 className="text-3xl md:text-4xl font-black text-red-500 tracking-tight">
                    Danger! Your message through the video is evil!
                  </h2>

                  <p className="text-stone-300 text-sm">
                    The software does not judge isolated words, but the overall message, moral thesis, or motto of this
                    video was evaluated to be contrary to divine moral law.
                  </p>
                </div>

                {/* Moral Breakdown Card */}
                <div className="w-full bg-black/60 border border-red-900/60 rounded-2xl p-6 text-left space-y-4">
                  <div>
                    <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-red-400 mb-1">
                      Commandment(s) Violated:
                    </h4>
                    <p className="text-white font-bold text-base">
                      {status?.morality_alert?.commandment_violated ||
                        'Violation of the Ten Commandments of Moses / Two Commandments of Christ'}
                    </p>
                  </div>

                  <div>
                    <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-red-400 mb-1">
                      Theological Reasoning &amp; Moral Law:
                    </h4>
                    <p className="text-stone-300 text-sm leading-relaxed whitespace-pre-wrap">
                      {status?.morality_alert?.reason ||
                        'The core concept and message taught by this video directly violates the Ten Commandments of the Law of Moses.'}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-red-900/40 text-[11px] text-stone-500 italic">
                    Rule of Morality Basis: Catholic Prayer Book (pages 98-100: Ten Commandments of Moses) and The Two
                    Commandments of Christ (St. Matthew 22:37-40; St. Mark 12:29-31).
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-col sm:flex-row gap-4 w-full max-w-md pt-2">
                  <Button
                    onClick={handleCancelAfterWarning}
                    className="flex-1 h-14 bg-red-600 hover:bg-red-700 text-white font-black text-base rounded-2xl shadow-xl shadow-red-950/50"
                  >
                    Discard Video &amp; Cancel
                  </Button>

                  <Button
                    variant="outline"
                    onClick={handleProceedDespiteWarning}
                    className="flex-1 h-14 border-stone-700 bg-stone-900/80 hover:bg-stone-800 text-amber-400 font-bold text-sm rounded-2xl"
                  >
                    Proceed Anyway (I Understand the Warning)
                  </Button>
                </div>
              </div>
            </motion.div>

          /* ── 4. Completed Screen ── */
          ) : status?.status === 'completed' ? (
            <motion.div
              key="completed"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-stone-950/80 backdrop-blur-xl border border-amber-500/20 rounded-3xl p-8 md:p-12 shadow-2xl"
            >
              <div className="flex flex-col md:flex-row gap-8 items-start">
                <div className="flex-1 space-y-6 w-full">
                  <div className="flex items-center gap-4 p-6 bg-amber-500/10 border border-amber-500/30 rounded-3xl">
                    <div className="w-12 h-12 bg-amber-500/20 rounded-full flex items-center justify-center">
                      <CheckCircle2 className="text-amber-400" size={28} />
                    </div>
                    <div>
                      <h3 className="font-black text-white text-xl tracking-tight">Your Captions are Ready</h3>
                      <p className="text-amber-500/70 text-xs font-bold uppercase tracking-widest">
                        {status?.video_burned
                          ? 'Burnt-in Video & .SRT Subtitles Produced'
                          : 'High-Precision .SRT File Ready'}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {status?.video_burned ? (
                      <>
                        <Button
                          onClick={handleDownloadBoth}
                          className="w-full h-16 text-lg font-black rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-600 hover:from-amber-600 hover:to-yellow-700 text-black shadow-xl shadow-amber-950/30"
                        >
                          <Download className="mr-2" size={22} /> Download Both (.mp4 + .srt)
                        </Button>

                        <div className="grid grid-cols-2 gap-3">
                          <Button
                            onClick={handleDownloadVideo}
                            className="h-12 text-sm font-bold rounded-xl bg-stone-900 border border-stone-800 hover:bg-stone-800 text-amber-300"
                          >
                            <PlayCircle className="mr-2" size={18} /> Video (.mp4)
                          </Button>
                          <Button
                            onClick={handleDownloadSrt}
                            className="h-12 text-sm font-bold rounded-xl bg-stone-900 border border-stone-800 hover:bg-stone-800 text-stone-200"
                          >
                            <Download className="mr-2" size={18} /> Subtitle (.srt)
                          </Button>
                        </div>
                      </>
                    ) : (
                      <Button
                        onClick={handleDownloadSrt}
                        className="w-full h-16 text-lg font-black rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-600 hover:from-amber-600 hover:to-yellow-700 text-black shadow-xl"
                      >
                        <Download className="mr-2" size={22} /> Download .SRT Subtitles
                      </Button>
                    )}

                    <Button
                      variant="ghost"
                      onClick={reset}
                      className="w-full text-stone-500 hover:text-white uppercase text-xs font-black tracking-widest"
                    >
                      Process Another Video
                    </Button>
                  </div>
                </div>

                <div className="flex-1 w-full h-[400px] bg-black/50 border border-stone-800 rounded-3xl overflow-hidden hidden md:block">
                  <div className="p-4 border-b border-stone-800 bg-white/[0.02] flex items-center justify-between">
                    <span className="text-xs font-bold text-amber-500/80 uppercase tracking-widest">SRT Preview</span>
                    <span className="text-[10px] text-stone-500">UTF-8 Standard SubRip</span>
                  </div>
                  <textarea
                    readOnly
                    value={srtContent}
                    className="w-full h-full bg-transparent p-6 text-stone-300 font-mono text-[11px] resize-none focus:outline-none scrollbar-hide"
                  />
                </div>
              </div>
            </motion.div>

          /* ── 5. Failed Screen (ONLY when status.status === 'failed') ── */
          ) : status?.status === 'failed' ? (
            <motion.div
              key="failed"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-stone-950/80 backdrop-blur-xl border border-red-500/20 rounded-3xl p-8 md:p-12 shadow-2xl"
            >
              <div className="text-center py-10 space-y-6">
                <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/20">
                  <AlertTriangle className="text-red-500" size={36} />
                </div>
                <div className="space-y-4">
                  <h3 className="font-black text-white text-3xl tracking-tight">Process Stopped</h3>
                  <p className="text-red-400 font-medium max-w-sm mx-auto p-4 bg-red-500/5 rounded-2xl border border-red-500/10 whitespace-pre-wrap text-sm">
                    {status?.error || 'An unexpected error occurred during processing.'}
                  </p>
                </div>
                <Button
                  onClick={reset}
                  className="px-8 h-12 bg-white text-black font-black uppercase tracking-tight rounded-full hover:bg-stone-200"
                >
                  Try Again
                </Button>
              </div>
            </motion.div>

          /* ── 6. Processing Screen (Default for ALL in-progress & transitional states) ── */
          ) : (
            <motion.div
              key="processing"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-stone-950/80 backdrop-blur-xl border border-amber-500/20 rounded-3xl p-8 md:p-12 shadow-2xl"
            >
              <div className="flex flex-col items-center space-y-8 py-4 text-center">
                <AnimatedDownload
                  progress={status?.progress || 0}
                  label={getStatusLabel(status?.status || '')}
                  className="mx-auto"
                  isAnimating={true}
                  timeRemaining={formatCountdown(countdownSecs)}
                />

                {/* Live Real-Time Countdown Badge */}
                <div className="flex items-center gap-2.5 px-5 py-2.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 font-mono text-sm shadow-inner">
                  <Clock size={16} className="animate-spin text-amber-400" />
                  <span>
                    Estimated Time Remaining:{' '}
                    <strong className="text-white text-base ml-1">{formatCountdown(countdownSecs)}</strong>
                  </span>
                </div>

                <div className="space-y-2">
                  <h3 className="font-black text-white text-3xl tracking-tight">
                    {status?.status === 'transcribing'
                      ? 'Transcribing Audio...'
                      : status?.status === 'generating_srt'
                      ? 'Generating Subtitles...'
                      : status?.status === 'checking_morality'
                      ? 'Evaluating Moral Message...'
                      : status?.status === 'embedding_captions'
                      ? 'Burning Captions into Video...'
                      : status?.status === 'extracting_audio'
                      ? 'Extracting Audio Track...'
                      : status?.status === 'detecting_language'
                      ? 'Detecting Spoken Language...'
                      : 'Processing Video...'}
                  </h3>
                  <p className="text-stone-500 text-sm font-medium">
                    Powered by Whisper large-v3-turbo engine with anti-hallucination speech filtering.
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-10 flex flex-wrap justify-center gap-6 text-stone-600 text-[10px] font-bold uppercase tracking-[0.2em]"
        >
          <span className="flex items-center gap-1.5">
            <CheckCircle2 size={12} className="text-amber-500/50" /> 99 Languages &amp; Accents
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 size={12} className="text-amber-500/50" /> Whisper large-v3-turbo
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 size={12} className="text-amber-500/50" /> Moral Law Check
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 size={12} className="text-amber-500/50" /> 100% On-Device Privacy
          </span>
        </motion.div>
      </motion.div>
    </div>
  );
}
