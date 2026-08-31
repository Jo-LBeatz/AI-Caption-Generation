import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Lock, ArrowRight, UserPlus, LogIn, Loader2 } from "lucide-react";
import axios from "axios";
import { Button } from "@/components/ui/button";

interface AuthPageProps {
  onAuthSuccess: (token: string, email: string) => void;
  apiBaseUrl: string;
}

export const AuthPage: React.FC<AuthPageProps> = ({ onAuthSuccess, apiBaseUrl }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/signup";
      const response = await axios.post(`${apiBaseUrl}${endpoint}`, { email, password });
      
      const { token, email: userEmail } = response.data;
      onAuthSuccess(token, userEmail);
    } catch (err: any) {
      setError(err.response?.data?.detail || "An authentication error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto">
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="bg-stone-900/50 backdrop-blur-xl border border-white/5 rounded-3xl p-8 md:p-10 shadow-2xl relative overflow-hidden"
      >
        {/* Glow Effect */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-64 bg-amber-500/10 blur-[120px] pointer-events-none rounded-full" />

        <div className="text-center mb-8 relative flex flex-col items-center">
          <img
            src="/logo.png"
            alt="RegulaVitae Emblem"
            className="w-16 h-16 mb-3 rounded-2xl border border-amber-500/30 shadow-lg shadow-amber-500/20 object-cover"
          />
          <h2 className="text-3xl font-black text-white tracking-tighter mb-2">
            {isLogin ? "Welcome Back" : "Create Account"}
          </h2>
          <p className="text-stone-400 text-sm font-medium">
            {isLogin 
              ? "Sign in to continue your transcriptions." 
              : "Sign up to start transcribing your videos."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 relative">
          <div className="space-y-4">
            <div className="relative group">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-500 group-focus-within:text-amber-500 transition-colors" size={18} />
              <input
                type="email"
                placeholder="Email Address"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-14 bg-black/40 border border-white/5 rounded-2xl pl-12 pr-4 text-white placeholder:text-stone-600 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all font-medium"
              />
            </div>
            <div className="relative group">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-500 group-focus-within:text-amber-500 transition-colors" size={18} />
              <input
                type="password"
                placeholder="Password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-14 bg-black/40 border border-white/5 rounded-2xl pl-12 pr-4 text-white placeholder:text-stone-600 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all font-medium"
              />
            </div>
          </div>

          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400 text-xs font-bold text-center"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full h-14 bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 text-white font-black text-lg rounded-2xl shadow-lg shadow-amber-900/20 transition-all hover:scale-[1.02] active:scale-[0.98] group"
          >
            {isLoading ? (
              <Loader2 className="animate-spin mr-2" size={20} />
            ) : isLogin ? (
              <>
                Sign In <LogIn className="ml-2 group-hover:translate-x-1 transition-transform" size={20} />
              </>
            ) : (
              <>
                Sign Up <UserPlus className="ml-2 group-hover:translate-x-1 transition-transform" size={20} />
              </>
            )}
          </Button>

          <div className="pt-4 text-center">
            <button
              type="button"
              onClick={() => {
                setIsLogin(!isLogin);
                setError(null);
              }}
              className="text-stone-500 hover:text-amber-500 text-sm font-bold transition-colors inline-flex items-center"
            >
              {isLogin ? "Don't have an account? Sign Up" : "Already have an account? Sign In"}
              <ArrowRight className="ml-1.5" size={14} />
            </button>
          </div>
        </form>
      </motion.div>

      <div className="mt-8 text-center text-stone-600 text-[10px] font-black uppercase tracking-[0.2em] space-y-2">
        <p>Private & Secure Experience</p>
        <p>Your data stays between you and the system</p>
      </div>
    </div>
  );
};
