import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Sliders,
  Check,
  Type,
  Palette,
  Layers,
  MoveVertical,
  CaseSensitive,
  ChevronDown,
  Eye,
  ShieldCheck,
} from 'lucide-react';

export interface CaptionStyleConfig {
  preset: 'classic' | 'sacred_gold' | 'cinematic_box' | 'yellow_pop' | 'bold_impact' | 'minimalist';
  font_name: string;
  font_size: number;
  primary_color: string;
  outline_color: string;
  outline_width: number;
  border_style: number; // 1 = outline + shadow, 3 = opaque/translucent box
  shadow_depth: number;
  back_color: string;
  back_opacity: number;
  bold: boolean;
  italic: boolean;
  uppercase: boolean;
  alignment: number; // 2 = bottom center, 8 = top center
  margin_v: number;
}

export interface PresetMeta {
  id: CaptionStyleConfig['preset'];
  name: string;
  tagline: string;
  font: string;
  textColor: string;
  bgDesc: string;
  previewClass: string;
  config: CaptionStyleConfig;
}

export const CAPTION_PRESETS: PresetMeta[] = [
  {
    id: 'classic',
    name: 'Classic Subtitle',
    tagline: 'Standard movie & documentary subtitle',
    font: 'Arial, sans-serif',
    textColor: '#FFFFFF',
    bgDesc: 'Crisp text with soft outline',
    previewClass: 'font-sans font-medium',
    config: {
      preset: 'classic',
      font_name: 'Arial',
      font_size: 13,
      primary_color: '#FFFFFF',
      outline_color: '#000000',
      outline_width: 1.2,
      border_style: 1,
      shadow_depth: 0.8,
      back_color: '#000000',
      back_opacity: 0.0,
      bold: false,
      italic: false,
      uppercase: false,
      alignment: 2,
      margin_v: 24,
    },
  },
  {
    id: 'sacred_gold',
    name: 'Sacred Gold',
    tagline: 'Warm amber glow · Verbum signature',
    font: 'Georgia, serif',
    textColor: '#FFD700',
    bgDesc: 'Warm serif with deep dark outline',
    previewClass: 'font-serif font-medium',
    config: {
      preset: 'sacred_gold',
      font_name: 'Georgia',
      font_size: 13,
      primary_color: '#FFD700',
      outline_color: '#1A0F00',
      outline_width: 1.2,
      border_style: 1,
      shadow_depth: 0.8,
      back_color: '#000000',
      back_opacity: 0.0,
      bold: false,
      italic: false,
      uppercase: false,
      alignment: 2,
      margin_v: 24,
    },
  },
  {
    id: 'cinematic_box',
    name: 'Cinematic Box',
    tagline: 'Netflix / Prime translucent dark backing',
    font: 'Arial, sans-serif',
    textColor: '#FFFFFF',
    bgDesc: 'Ultra-legible dark box backing',
    previewClass: 'font-sans font-semibold',
    config: {
      preset: 'cinematic_box',
      font_name: 'Arial',
      font_size: 12,
      primary_color: '#FFFFFF',
      outline_color: '#000000',
      outline_width: 0.0,
      border_style: 3,
      shadow_depth: 0.0,
      back_color: '#000000',
      back_opacity: 0.65,
      bold: false,
      italic: false,
      uppercase: false,
      alignment: 2,
      margin_v: 24,
    },
  },
  {
    id: 'yellow_pop',
    name: 'Yellow Pop',
    tagline: 'High-contrast educational / explainer',
    font: 'Trebuchet MS, sans-serif',
    textColor: '#FFF000',
    bgDesc: 'Punchy bright yellow with solid outline',
    previewClass: 'font-sans font-bold',
    config: {
      preset: 'yellow_pop',
      font_name: 'Trebuchet MS',
      font_size: 13,
      primary_color: '#FFF000',
      outline_color: '#000000',
      outline_width: 1.4,
      border_style: 1,
      shadow_depth: 0.8,
      back_color: '#000000',
      back_opacity: 0.0,
      bold: false,
      italic: false,
      uppercase: false,
      alignment: 2,
      margin_v: 24,
    },
  },
  {
    id: 'bold_impact',
    name: 'Bold Modern',
    tagline: 'Punchy creator & reel uppercase text',
    font: 'Trebuchet MS, sans-serif',
    textColor: '#FFFFFF',
    bgDesc: 'Bold uppercase text with crisp shadow',
    previewClass: 'font-sans font-black uppercase tracking-wider',
    config: {
      preset: 'bold_impact',
      font_name: 'Trebuchet MS',
      font_size: 13,
      primary_color: '#FFFFFF',
      outline_color: '#000000',
      outline_width: 1.6,
      border_style: 1,
      shadow_depth: 1.0,
      back_color: '#000000',
      back_opacity: 0.0,
      bold: true,
      italic: false,
      uppercase: true,
      alignment: 2,
      margin_v: 24,
    },
  },
  {
    id: 'minimalist',
    name: 'Minimalist White',
    tagline: 'Restrained, delicate & quiet elegance',
    font: 'Segoe UI, sans-serif',
    textColor: '#F1F5F9',
    bgDesc: 'Delicate off-white, slim outline',
    previewClass: 'font-sans font-normal',
    config: {
      preset: 'minimalist',
      font_name: 'Segoe UI',
      font_size: 12,
      primary_color: '#F1F5F9',
      outline_color: '#0F172A',
      outline_width: 0.8,
      border_style: 1,
      shadow_depth: 0.0,
      back_color: '#000000',
      back_opacity: 0.0,
      bold: false,
      italic: false,
      uppercase: false,
      alignment: 2,
      margin_v: 22,
    },
  },
];

interface CaptionStylePickerProps {
  value: CaptionStyleConfig;
  onChange: (newStyle: CaptionStyleConfig) => void;
  sampleText?: string;
}

export function CaptionStylePicker({
  value,
  onChange,
  sampleText = 'In the beginning was the Word, and the Word was with God.',
}: CaptionStylePickerProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSelectPreset = (presetId: CaptionStyleConfig['preset']) => {
    const found = CAPTION_PRESETS.find((p) => p.id === presetId);
    if (found) {
      onChange({ ...found.config });
    }
  };

  const updateConfig = (patch: Partial<CaptionStyleConfig>) => {
    onChange({ ...value, ...patch });
  };

  const currentPreset = CAPTION_PRESETS.find((p) => p.id === value.preset) || CAPTION_PRESETS[0];

  // Derive CSS style for the live preview text
  const previewTextStyle: React.CSSProperties = {
    fontFamily:
      value.font_name === 'Georgia'
        ? 'Georgia, serif'
        : value.font_name === 'Trebuchet MS'
        ? '"Trebuchet MS", sans-serif'
        : value.font_name === 'Segoe UI'
        ? '"Segoe UI", sans-serif'
        : 'Arial, sans-serif',
    color: value.primary_color,
    fontSize: value.font_size === 11 ? '13px' : value.font_size === 15 ? '17px' : '15px',
    fontWeight: value.bold ? 800 : 600,
    fontStyle: value.italic ? 'italic' : 'normal',
    textTransform: value.uppercase ? 'uppercase' : 'none',
    letterSpacing: value.uppercase ? '0.05em' : 'normal',
    lineHeight: 1.35,
    maxWidth: '90%',
    textAlign: 'center',
    padding: value.border_style === 3 ? '4px 10px' : '2px 6px',
    borderRadius: value.border_style === 3 ? '6px' : '0',
    backgroundColor:
      value.border_style === 3
        ? `rgba(0, 0, 0, ${value.back_opacity || 0.65})`
        : 'transparent',
    textShadow:
      value.border_style === 3
        ? 'none'
        : `-1px -1px 0 ${value.outline_color}, 1px -1px 0 ${value.outline_color}, -1px 1px 0 ${value.outline_color}, 1px 1px 0 ${value.outline_color}, 0 2px 4px rgba(0,0,0,0.8)`,
  };

  return (
    <div className="w-full space-y-5 bg-stone-900/40 border border-stone-800/80 rounded-3xl p-5 md:p-6 text-left">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-stone-800/60 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
            <Sparkles size={16} className="text-amber-400" />
          </div>
          <div>
            <h4 className="text-white font-black text-base tracking-tight flex items-center gap-2">
              Caption Style &amp; Aesthetics
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                True Subtitles
              </span>
            </h4>
            <p className="text-stone-400 text-xs">
              Sized as authentic subtitles — comfortable, clean, and never oversized in burnt video.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1.5 text-xs font-bold text-amber-400 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 px-3 py-1.5 rounded-full border border-amber-500/20 transition-all"
        >
          <Sliders size={13} />
          {showAdvanced ? 'Hide Customizer' : 'Customize Aesthetics'}
          <ChevronDown
            size={13}
            className={`transition-transform duration-200 ${showAdvanced ? 'rotate-180' : ''}`}
          />
        </button>
      </div>

      {/* ── 1. Live Interactive Video Subtitle Preview ── */}
      <div className="relative w-full aspect-[21/9] sm:aspect-[24/9] rounded-2xl overflow-hidden border border-stone-800 shadow-2xl bg-black flex flex-col justify-between p-4 group">
        {/* Cinematic Backdrop Simulator */}
        <div className="absolute inset-0 bg-gradient-to-tr from-stone-950 via-stone-900 to-amber-950/40 opacity-90" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-amber-950/20 via-black/40 to-black/80" />

        {/* Video Canvas Badge */}
        <div className="relative z-10 flex items-center justify-between text-[11px] text-stone-400">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/10 font-mono text-[10px] text-stone-300">
            <Eye size={12} className="text-amber-400" />
            Live Preview · {currentPreset.name} ({value.font_size}pt Subtitle)
          </span>

          <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-amber-400/80 font-bold uppercase tracking-wider">
            <ShieldCheck size={12} /> Standard Subtitle Proportion
          </span>
        </div>

        {/* Subtitle Positioning Container */}
        <div
          className={`relative z-10 w-full flex justify-center items-center ${
            value.alignment === 8 ? 'mt-2 mb-auto' : 'mt-auto mb-2'
          }`}
        >
          <span style={previewTextStyle}>{sampleText}</span>
        </div>
      </div>

      {/* ── 2. Preset Selection Cards ── */}
      <div className="space-y-2">
        <label className="text-xs font-black text-stone-400 uppercase tracking-widest flex items-center gap-1.5">
          <Layers size={13} />
          Choose Subtitle Preset
        </label>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {CAPTION_PRESETS.map((preset) => {
            const isSelected = value.preset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => handleSelectPreset(preset.id)}
                className={`flex flex-col justify-between p-3 rounded-2xl border text-left transition-all ${
                  isSelected
                    ? 'bg-amber-500/15 border-amber-500 text-white shadow-lg shadow-amber-950/40 ring-1 ring-amber-500/50'
                    : 'bg-stone-950/60 border-stone-800/80 text-stone-400 hover:bg-stone-900/60 hover:border-stone-700 hover:text-stone-200'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div
                    className="w-4 h-4 rounded-full border border-black/40 shadow-sm"
                    style={{ backgroundColor: preset.textColor }}
                  />
                  {isSelected && (
                    <div className="w-4 h-4 rounded-full bg-amber-500 flex items-center justify-center text-black">
                      <Check size={10} className="stroke-[3]" />
                    </div>
                  )}
                </div>

                <div>
                  <div className={`font-bold text-xs truncate ${isSelected ? 'text-amber-400' : 'text-stone-200'}`}>
                    {preset.name}
                  </div>
                  <div className="text-[10px] text-stone-500 truncate mt-0.5">{preset.tagline}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 3. Advanced Customizer Drawer ── */}
      <AnimatePresence>
        {showAdvanced && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="pt-3 border-t border-stone-800/60 space-y-4 overflow-hidden"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Font Family */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-stone-400 uppercase tracking-wider flex items-center gap-1">
                  <Type size={12} /> Font Family
                </label>
                <select
                  value={value.font_name}
                  onChange={(e) => updateConfig({ font_name: e.target.value })}
                  className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2 text-xs font-semibold text-white focus:outline-none focus:border-amber-500"
                >
                  <option value="Arial">Arial (Clean Modern Sans)</option>
                  <option value="Georgia">Georgia (Sacred Classic Serif)</option>
                  <option value="Trebuchet MS">Trebuchet MS (Crisp Rounded)</option>
                  <option value="Segoe UI">Segoe UI (Minimalist Smooth)</option>
                </select>
              </div>

              {/* Subtitle Sizing */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-stone-400 uppercase tracking-wider flex items-center gap-1">
                  <Sliders size={12} /> Subtitle Size
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    { label: 'Subtle', size: 11 },
                    { label: 'Standard', size: 13 },
                    { label: 'Clear', size: 15 },
                  ].map((s) => (
                    <button
                      key={s.size}
                      type="button"
                      onClick={() => updateConfig({ font_size: s.size })}
                      className={`py-1.5 text-xs font-bold rounded-lg border transition-all ${
                        value.font_size === s.size
                          ? 'bg-amber-500 text-black border-amber-500'
                          : 'bg-stone-950 border-stone-800 text-stone-400 hover:text-white'
                      }`}
                    >
                      {s.label} ({s.size}pt)
                    </button>
                  ))}
                </div>
              </div>

              {/* Text Primary Color */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-stone-400 uppercase tracking-wider flex items-center gap-1">
                  <Palette size={12} /> Text Color
                </label>
                <div className="flex items-center gap-2">
                  {[
                    { label: 'White', color: '#FFFFFF' },
                    { label: 'Sacred Gold', color: '#FFD700' },
                    { label: 'Yellow', color: '#FFF000' },
                    { label: 'Amber', color: '#F59E0B' },
                    { label: 'Cyan', color: '#00E5FF' },
                  ].map((c) => (
                    <button
                      key={c.color}
                      type="button"
                      title={c.label}
                      onClick={() => updateConfig({ primary_color: c.color })}
                      className={`w-7 h-7 rounded-full border-2 transition-transform ${
                        value.primary_color === c.color
                          ? 'border-amber-400 scale-110 shadow-md ring-2 ring-amber-400/20'
                          : 'border-stone-700 hover:scale-105'
                      }`}
                      style={{ backgroundColor: c.color }}
                    />
                  ))}
                </div>
              </div>

              {/* Backing Box vs Outline */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-stone-400 uppercase tracking-wider flex items-center gap-1">
                  <Layers size={12} /> Backing Style
                </label>
                <select
                  value={value.border_style === 3 ? 'box' : 'outline'}
                  onChange={(e) => {
                    if (e.target.value === 'box') {
                      updateConfig({ border_style: 3, back_opacity: 0.65, outline_width: 0 });
                    } else {
                      updateConfig({ border_style: 1, back_opacity: 0, outline_width: 1.2 });
                    }
                  }}
                  className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2 text-xs font-semibold text-white focus:outline-none focus:border-amber-500"
                >
                  <option value="outline">Clean Outline &amp; Shadow</option>
                  <option value="box">Translucent Box Backing (Netflix Style)</option>
                </select>
              </div>
            </div>

            {/* Letter Case & Position */}
            <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-stone-800/40 text-xs">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={value.uppercase}
                  onChange={(e) => updateConfig({ uppercase: e.target.checked })}
                  className="rounded border-stone-700 bg-stone-950 text-amber-500 focus:ring-0"
                />
                <span className="font-semibold text-stone-300 flex items-center gap-1">
                  <CaseSensitive size={14} /> Transform to ALL CAPS
                </span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={value.bold}
                  onChange={(e) => updateConfig({ bold: e.target.checked })}
                  className="rounded border-stone-700 bg-stone-950 text-amber-500 focus:ring-0"
                />
                <span className="font-semibold text-stone-300">Bold Subtitles</span>
              </label>

              <div className="flex items-center gap-2 ml-auto">
                <span className="font-bold text-stone-400 flex items-center gap-1">
                  <MoveVertical size={13} /> Position:
                </span>
                <button
                  type="button"
                  onClick={() => updateConfig({ alignment: 2, margin_v: 24 })}
                  className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${
                    value.alignment === 2 && value.margin_v === 24
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300'
                      : 'bg-stone-950 border-stone-800 text-stone-500'
                  }`}
                >
                  Lower Third (Default)
                </button>
                <button
                  type="button"
                  onClick={() => updateConfig({ alignment: 2, margin_v: 48 })}
                  className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${
                    value.alignment === 2 && value.margin_v === 48
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300'
                      : 'bg-stone-950 border-stone-800 text-stone-500'
                  }`}
                >
                  Raised (Reels/Shorts Safe)
                </button>
                <button
                  type="button"
                  onClick={() => updateConfig({ alignment: 8, margin_v: 24 })}
                  className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${
                    value.alignment === 8
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300'
                      : 'bg-stone-950 border-stone-800 text-stone-500'
                  }`}
                >
                  Top
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
