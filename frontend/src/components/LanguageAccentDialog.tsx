import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Globe, Mic2, ChevronDown, CheckCircle2, Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CAPTION_PRESETS, type CaptionStyleConfig } from '@/components/CaptionStylePicker';

// ---------------------------------------------------------------------------
// Language data — all 99 Whisper-supported languages
// ---------------------------------------------------------------------------
export interface WhisperLanguage {
  code: string;
  name: string;
  flag: string;
  nativeName?: string;
}

export const WHISPER_LANGUAGES: WhisperLanguage[] = [
  { code: 'en', name: 'English', flag: '🇬🇧', nativeName: 'English' },
  { code: 'zh', name: 'Chinese', flag: '🇨🇳', nativeName: '中文' },
  { code: 'de', name: 'German', flag: '🇩🇪', nativeName: 'Deutsch' },
  { code: 'es', name: 'Spanish', flag: '🇪🇸', nativeName: 'Español' },
  { code: 'ru', name: 'Russian', flag: '🇷🇺', nativeName: 'Русский' },
  { code: 'ko', name: 'Korean', flag: '🇰🇷', nativeName: '한국어' },
  { code: 'fr', name: 'French', flag: '🇫🇷', nativeName: 'Français' },
  { code: 'ja', name: 'Japanese', flag: '🇯🇵', nativeName: '日本語' },
  { code: 'pt', name: 'Portuguese', flag: '🇵🇹', nativeName: 'Português' },
  { code: 'tr', name: 'Turkish', flag: '🇹🇷', nativeName: 'Türkçe' },
  { code: 'pl', name: 'Polish', flag: '🇵🇱', nativeName: 'Polski' },
  { code: 'ca', name: 'Catalan', flag: '🏴', nativeName: 'Català' },
  { code: 'nl', name: 'Dutch', flag: '🇳🇱', nativeName: 'Nederlands' },
  { code: 'ar', name: 'Arabic', flag: '🇸🇦', nativeName: 'العربية' },
  { code: 'sv', name: 'Swedish', flag: '🇸🇪', nativeName: 'Svenska' },
  { code: 'it', name: 'Italian', flag: '🇮🇹', nativeName: 'Italiano' },
  { code: 'id', name: 'Indonesian', flag: '🇮🇩', nativeName: 'Bahasa Indonesia' },
  { code: 'hi', name: 'Hindi', flag: '🇮🇳', nativeName: 'हिन्दी' },
  { code: 'fi', name: 'Finnish', flag: '🇫🇮', nativeName: 'Suomi' },
  { code: 'vi', name: 'Vietnamese', flag: '🇻🇳', nativeName: 'Tiếng Việt' },
  { code: 'he', name: 'Hebrew', flag: '🇮🇱', nativeName: 'עברית' },
  { code: 'uk', name: 'Ukrainian', flag: '🇺🇦', nativeName: 'Українська' },
  { code: 'el', name: 'Greek', flag: '🇬🇷', nativeName: 'Ελληνικά' },
  { code: 'ms', name: 'Malay', flag: '🇲🇾', nativeName: 'Bahasa Melayu' },
  { code: 'cs', name: 'Czech', flag: '🇨🇿', nativeName: 'Čeština' },
  { code: 'ro', name: 'Romanian', flag: '🇷🇴', nativeName: 'Română' },
  { code: 'da', name: 'Danish', flag: '🇩🇰', nativeName: 'Dansk' },
  { code: 'hu', name: 'Hungarian', flag: '🇭🇺', nativeName: 'Magyar' },
  { code: 'ta', name: 'Tamil', flag: '🇮🇳', nativeName: 'தமிழ்' },
  { code: 'no', name: 'Norwegian', flag: '🇳🇴', nativeName: 'Norsk' },
  { code: 'th', name: 'Thai', flag: '🇹🇭', nativeName: 'ภาษาไทย' },
  { code: 'ur', name: 'Urdu', flag: '🇵🇰', nativeName: 'اردو' },
  { code: 'hr', name: 'Croatian', flag: '🇭🇷', nativeName: 'Hrvatski' },
  { code: 'bg', name: 'Bulgarian', flag: '🇧🇬', nativeName: 'Български' },
  { code: 'lt', name: 'Lithuanian', flag: '🇱🇹', nativeName: 'Lietuvių' },
  { code: 'la', name: 'Latin', flag: '🏛️', nativeName: 'Latina' },
  { code: 'mi', name: 'Maori', flag: '🇳🇿', nativeName: 'Te Reo Māori' },
  { code: 'ml', name: 'Malayalam', flag: '🇮🇳', nativeName: 'മലയാളം' },
  { code: 'cy', name: 'Welsh', flag: '🏴󠁧󠁢󠁷󠁬󠁳󠁿', nativeName: 'Cymraeg' },
  { code: 'sk', name: 'Slovak', flag: '🇸🇰', nativeName: 'Slovenčina' },
  { code: 'te', name: 'Telugu', flag: '🇮🇳', nativeName: 'తెలుగు' },
  { code: 'fa', name: 'Persian', flag: '🇮🇷', nativeName: 'فارسی' },
  { code: 'lv', name: 'Latvian', flag: '🇱🇻', nativeName: 'Latviešu' },
  { code: 'bn', name: 'Bengali', flag: '🇧🇩', nativeName: 'বাংলা' },
  { code: 'sr', name: 'Serbian', flag: '🇷🇸', nativeName: 'Српски' },
  { code: 'az', name: 'Azerbaijani', flag: '🇦🇿', nativeName: 'Azərbaycan' },
  { code: 'sl', name: 'Slovenian', flag: '🇸🇮', nativeName: 'Slovenščina' },
  { code: 'kn', name: 'Kannada', flag: '🇮🇳', nativeName: 'ಕನ್ನಡ' },
  { code: 'et', name: 'Estonian', flag: '🇪🇪', nativeName: 'Eesti' },
  { code: 'mk', name: 'Macedonian', flag: '🇲🇰', nativeName: 'Македонски' },
  { code: 'br', name: 'Breton', flag: '🏴', nativeName: 'Brezhoneg' },
  { code: 'eu', name: 'Basque', flag: '🏴', nativeName: 'Euskara' },
  { code: 'is', name: 'Icelandic', flag: '🇮🇸', nativeName: 'Íslenska' },
  { code: 'hy', name: 'Armenian', flag: '🇦🇲', nativeName: 'Հայերեն' },
  { code: 'ne', name: 'Nepali', flag: '🇳🇵', nativeName: 'नेपाली' },
  { code: 'mn', name: 'Mongolian', flag: '🇲🇳', nativeName: 'Монгол' },
  { code: 'bs', name: 'Bosnian', flag: '🇧🇦', nativeName: 'Bosanski' },
  { code: 'kk', name: 'Kazakh', flag: '🇰🇿', nativeName: 'Қазақша' },
  { code: 'sq', name: 'Albanian', flag: '🇦🇱', nativeName: 'Shqip' },
  { code: 'sw', name: 'Swahili', flag: '🇹🇿', nativeName: 'Kiswahili' },
  { code: 'gl', name: 'Galician', flag: '🏴', nativeName: 'Galego' },
  { code: 'mr', name: 'Marathi', flag: '🇮🇳', nativeName: 'मराठी' },
  { code: 'pa', name: 'Punjabi', flag: '🇮🇳', nativeName: 'ਪੰਜਾਬੀ' },
  { code: 'si', name: 'Sinhala', flag: '🇱🇰', nativeName: 'සිංහල' },
  { code: 'km', name: 'Khmer', flag: '🇰🇭', nativeName: 'ភាសាខ្មែរ' },
  { code: 'sn', name: 'Shona', flag: '🇿🇼', nativeName: 'chiShona' },
  { code: 'yo', name: 'Yoruba', flag: '🇳🇬', nativeName: 'Yorùbá' },
  { code: 'so', name: 'Somali', flag: '🇸🇴', nativeName: 'Soomaali' },
  { code: 'af', name: 'Afrikaans', flag: '🇿🇦', nativeName: 'Afrikaans' },
  { code: 'oc', name: 'Occitan', flag: '🏴', nativeName: 'Occitan' },
  { code: 'ka', name: 'Georgian', flag: '🇬🇪', nativeName: 'ქართული' },
  { code: 'be', name: 'Belarusian', flag: '🇧🇾', nativeName: 'Беларуская' },
  { code: 'tg', name: 'Tajik', flag: '🇹🇯', nativeName: 'Тоҷикӣ' },
  { code: 'sd', name: 'Sindhi', flag: '🇵🇰', nativeName: 'سنڌي' },
  { code: 'gu', name: 'Gujarati', flag: '🇮🇳', nativeName: 'ગુજરાતી' },
  { code: 'am', name: 'Amharic', flag: '🇪🇹', nativeName: 'አማርኛ' },
  { code: 'yi', name: 'Yiddish', flag: '🕍', nativeName: 'ייִדיש' },
  { code: 'lo', name: 'Lao', flag: '🇱🇦', nativeName: 'ລາວ' },
  { code: 'uz', name: 'Uzbek', flag: '🇺🇿', nativeName: "O'zbek" },
  { code: 'fo', name: 'Faroese', flag: '🇫🇴', nativeName: 'Føroyskt' },
  { code: 'ht', name: 'Haitian Creole', flag: '🇭🇹', nativeName: 'Kreyòl ayisyen' },
  { code: 'ps', name: 'Pashto', flag: '🇦🇫', nativeName: 'پښتو' },
  { code: 'tk', name: 'Turkmen', flag: '🇹🇲', nativeName: 'Türkmen' },
  { code: 'nn', name: 'Nynorsk', flag: '🇳🇴', nativeName: 'Nynorsk' },
  { code: 'mt', name: 'Maltese', flag: '🇲🇹', nativeName: 'Malti' },
  { code: 'sa', name: 'Sanskrit', flag: '🕉️', nativeName: 'संस्कृत' },
  { code: 'lb', name: 'Luxembourgish', flag: '🇱🇺', nativeName: 'Lëtzebuergesch' },
  { code: 'my', name: 'Myanmar', flag: '🇲🇲', nativeName: 'မြန်မာ' },
  { code: 'bo', name: 'Tibetan', flag: '🏔️', nativeName: 'བོད་སྐད།' },
  { code: 'tl', name: 'Tagalog', flag: '🇵🇭', nativeName: 'Tagalog' },
  { code: 'mg', name: 'Malagasy', flag: '🇲🇬', nativeName: 'Malagasy' },
  { code: 'as', name: 'Assamese', flag: '🇮🇳', nativeName: 'অসমীয়া' },
  { code: 'tt', name: 'Tatar', flag: '🏴', nativeName: 'Татар' },
  { code: 'haw', name: 'Hawaiian', flag: '🌺', nativeName: 'ʻŌlelo Hawaiʻi' },
  { code: 'ln', name: 'Lingala', flag: '🇨🇩', nativeName: 'Lingála' },
  { code: 'ha', name: 'Hausa', flag: '🇳🇬', nativeName: 'Hausa' },
  { code: 'ba', name: 'Bashkir', flag: '🏴', nativeName: 'Башҡортса' },
  { code: 'jw', name: 'Javanese', flag: '🇮🇩', nativeName: 'Basa Jawa' },
  { code: 'su', name: 'Sundanese', flag: '🇮🇩', nativeName: 'Basa Sunda' },
];

// ---------------------------------------------------------------------------
// Accent / dialect data per language
// ---------------------------------------------------------------------------
export interface AccentVariant {
  id: string;
  label: string;
  description?: string;
}

export const ACCENT_VARIANTS: Record<string, AccentVariant[]> = {
  en: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'en_american', label: '🇺🇸 American English', description: 'General American accent' },
    { id: 'en_british', label: '🇬🇧 British English', description: 'Received Pronunciation / RP' },
    { id: 'en_australian', label: '🇦🇺 Australian English', description: 'General Australian accent' },
    { id: 'en_indian', label: '🇮🇳 Indian English', description: 'Indian subcontinent English' },
    { id: 'en_irish', label: '🇮🇪 Irish English', description: 'Irish accent and dialect' },
    { id: 'en_scottish', label: '🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish English', description: 'Scottish accent' },
    { id: 'en_south_african', label: '🇿🇦 South African English', description: 'South African accent' },
    { id: 'en_canadian', label: '🇨🇦 Canadian English', description: 'Canadian pronunciation' },
    { id: 'en_caribbean', label: '🌴 Caribbean English', description: 'Caribbean dialect' },
  ],
  es: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'es_castilian', label: '🇪🇸 Castilian Spanish', description: 'Spain standard Spanish' },
    { id: 'es_mexican', label: '🇲🇽 Mexican Spanish', description: 'Mexican accent' },
    { id: 'es_argentinian', label: '🇦🇷 Argentine Spanish', description: 'Rioplatense accent' },
    { id: 'es_colombian', label: '🇨🇴 Colombian Spanish', description: 'Colombian accent' },
    { id: 'es_chilean', label: '🇨🇱 Chilean Spanish', description: 'Chilean accent' },
  ],
  fr: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'fr_standard', label: '🇫🇷 Metropolitan French', description: 'Standard French from France' },
    { id: 'fr_canadian', label: '🇨🇦 Quebec French', description: 'Canadian French accent' },
    { id: 'fr_belgian', label: '🇧🇪 Belgian French', description: 'Belgian French accent' },
    { id: 'fr_swiss', label: '🇨🇭 Swiss French', description: 'Swiss French accent' },
  ],
  ar: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'ar_msa', label: '📖 Modern Standard Arabic', description: 'Fusha / formal Arabic' },
    { id: 'ar_egyptian', label: '🇪🇬 Egyptian Arabic', description: 'Egyptian dialect' },
    { id: 'ar_levantine', label: '🇱🇧 Levantine Arabic', description: 'Syrian / Lebanese dialect' },
    { id: 'ar_gulf', label: '🇸🇦 Gulf Arabic', description: 'Gulf / Khaleeji dialect' },
    { id: 'ar_moroccan', label: '🇲🇦 Moroccan Darija', description: 'Moroccan Arabic dialect' },
  ],
  pt: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'pt_brazilian', label: '🇧🇷 Brazilian Portuguese', description: 'Brazilian accent' },
    { id: 'pt_european', label: '🇵🇹 European Portuguese', description: 'Portugal accent' },
  ],
  zh: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'zh_mandarin_simplified', label: '🇨🇳 Mandarin (Simplified)', description: 'Mainland China Mandarin' },
    { id: 'zh_mandarin_traditional', label: '🇹🇼 Mandarin (Traditional)', description: 'Taiwanese Mandarin' },
    { id: 'zh_cantonese', label: '🇭🇰 Cantonese', description: 'Hong Kong Cantonese' },
  ],
  de: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'de_standard', label: '🇩🇪 Hochdeutsch', description: 'Standard German' },
    { id: 'de_austrian', label: '🇦🇹 Austrian German', description: 'Austrian accent' },
    { id: 'de_swiss', label: '🇨🇭 Swiss German', description: 'Swiss German dialect' },
  ],
  hi: [
    { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide' },
    { id: 'hi_standard', label: '🇮🇳 Standard Hindi', description: 'Standard Khari Boli Hindi' },
    { id: 'hi_code_switch', label: '🔀 Hinglish', description: 'Hindi mixed with English' },
  ],
};

// Default accent (no accent hint) for languages without specific variants
const DEFAULT_ACCENTS: AccentVariant[] = [
  { id: 'none', label: 'Auto / Standard', description: 'Let Whisper decide automatically' },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface LanguageAccentDialogProps {
  detectedLanguage: string;
  detectedProbability: number;
  topCandidates: Array<{ language: string; probability: number }>;
  onConfirm: (language: string, accentId: string) => void;
  isConfirming: boolean;
  captionStyle?: CaptionStyleConfig;
  onCaptionStyleChange?: (style: CaptionStyleConfig) => void;
}

// ---------------------------------------------------------------------------
// Helper: get language info by code
// ---------------------------------------------------------------------------
function getLangInfo(code: string): WhisperLanguage {
  return (
    WHISPER_LANGUAGES.find((l) => l.code === code) || {
      code,
      name: code.toUpperCase(),
      flag: '🌐',
    }
  );
}

function getConfidenceColor(prob: number): string {
  if (prob >= 80) return 'text-emerald-400';
  if (prob >= 50) return 'text-amber-400';
  return 'text-red-400';
}

function getConfidenceLabel(prob: number): string {
  if (prob >= 90) return 'Very High Confidence';
  if (prob >= 70) return 'High Confidence';
  if (prob >= 50) return 'Moderate Confidence';
  return 'Low Confidence — Please Verify';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function LanguageAccentDialog({
  detectedLanguage,
  detectedProbability,
  topCandidates,
  onConfirm,
  isConfirming,
  captionStyle,
  onCaptionStyleChange,
}: LanguageAccentDialogProps) {
  const [selectedLangCode, setSelectedLangCode] = useState<string>(
    detectedLanguage === 'auto' ? 'en' : detectedLanguage
  );
  const [selectedAccentId, setSelectedAccentId] = useState<string>('none');
  const [langSearch, setLangSearch] = useState('');
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);

  const filteredLanguages = useMemo(() => {
    const q = langSearch.toLowerCase();
    if (!q) return WHISPER_LANGUAGES;
    return WHISPER_LANGUAGES.filter(
      (l) =>
        l.name.toLowerCase().includes(q) ||
        l.code.toLowerCase().includes(q) ||
        (l.nativeName || '').toLowerCase().includes(q)
    );
  }, [langSearch]);

  const accentOptions: AccentVariant[] =
    ACCENT_VARIANTS[selectedLangCode] || DEFAULT_ACCENTS;

  const selectedLang = getLangInfo(selectedLangCode);
  const detectedLang = getLangInfo(detectedLanguage);

  // Reset accent when language changes
  const handleLangChange = (code: string) => {
    setSelectedLangCode(code);
    setSelectedAccentId('none');
    setLangDropdownOpen(false);
    setLangSearch('');
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, y: 10 }}
      className="w-full space-y-6"
    >
      {/* Header */}
      <div className="text-center space-y-2 pb-2">
        <div className="inline-flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-full px-4 py-1.5 mb-2">
          <Globe size={14} className="text-amber-500" />
          <span className="text-xs font-black text-amber-400 uppercase tracking-widest">
            Language Detected
          </span>
        </div>
        <h2 className="text-2xl font-black text-white tracking-tight">
          Confirm Language &amp; Accent
        </h2>
        <p className="text-stone-500 text-sm">
          Whisper analysed your audio. Confirm or adjust for maximum accuracy.
        </p>
      </div>

      {/* Detection result card */}
      <div className="bg-stone-900/60 border border-white/8 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-1.5">
            <Mic2 size={12} className="text-amber-500/60" />
            Auto-Detected
          </span>
          <span className={`text-xs font-black uppercase tracking-wider ${getConfidenceColor(detectedProbability)}`}>
            {getConfidenceLabel(detectedProbability)}
          </span>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-4xl leading-none">{detectedLang.flag}</span>
          <div className="flex-1">
            <div className="flex items-baseline gap-3">
              <span className="text-xl font-black text-white">{detectedLang.name}</span>
              <span className={`text-2xl font-black ${getConfidenceColor(detectedProbability)}`}>
                {detectedProbability.toFixed(1)}%
              </span>
            </div>
            {detectedLang.nativeName && (
              <span className="text-stone-500 text-sm">{detectedLang.nativeName}</span>
            )}
          </div>
        </div>

        {/* Top candidates mini-bar */}
        {topCandidates.length > 1 && (
          <div className="mt-4 space-y-1.5">
            <span className="text-[10px] font-black text-stone-600 uppercase tracking-widest">
              Other candidates
            </span>
            <div className="flex flex-wrap gap-2">
              {topCandidates.slice(1, 4).map((c) => {
                const ci = getLangInfo(c.language);
                return (
                  <button
                    key={c.language}
                    onClick={() => handleLangChange(c.language)}
                    className="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 border border-white/8 rounded-lg px-2.5 py-1 text-xs font-bold text-stone-400 hover:text-white transition-all"
                  >
                    <span>{ci.flag}</span>
                    <span>{ci.name}</span>
                    <span className="text-stone-600">{c.probability.toFixed(0)}%</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Language selector */}
      <div className="space-y-2">
        <label className="text-xs font-black text-stone-400 uppercase tracking-widest flex items-center gap-1.5">
          <Globe size={12} />
          Language
        </label>
        <div className="relative">
          <button
            onClick={() => setLangDropdownOpen(!langDropdownOpen)}
            className="w-full flex items-center justify-between gap-3 bg-stone-900/60 hover:bg-stone-900/80 border border-white/8 hover:border-white/15 rounded-xl px-4 py-3 text-left transition-all"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl leading-none">{selectedLang.flag}</span>
              <div>
                <div className="font-black text-white text-sm">{selectedLang.name}</div>
                {selectedLang.nativeName && (
                  <div className="text-stone-500 text-xs">{selectedLang.nativeName}</div>
                )}
              </div>
            </div>
            <ChevronDown
              size={16}
              className={`text-stone-500 transition-transform ${langDropdownOpen ? 'rotate-180' : ''}`}
            />
          </button>

          <AnimatePresence>
            {langDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="absolute top-full mt-2 left-0 right-0 z-50 bg-[#0d0d0c] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
              >
                {/* Search */}
                <div className="p-3 border-b border-white/8">
                  <div className="flex items-center gap-2 bg-white/5 rounded-xl px-3 py-2">
                    <Search size={14} className="text-stone-500" />
                    <input
                      autoFocus
                      value={langSearch}
                      onChange={(e) => setLangSearch(e.target.value)}
                      placeholder="Search language..."
                      className="bg-transparent flex-1 text-sm text-white placeholder-stone-600 outline-none"
                    />
                  </div>
                </div>
                {/* List */}
                <div className="max-h-56 overflow-y-auto scrollbar-hide py-2">
                  {filteredLanguages.length === 0 ? (
                    <div className="text-center py-6 text-stone-600 text-sm">No languages found</div>
                  ) : (
                    filteredLanguages.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => handleLangChange(lang.code)}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition-colors text-left ${
                          selectedLangCode === lang.code ? 'bg-amber-500/10' : ''
                        }`}
                      >
                        <span className="text-xl leading-none w-7">{lang.flag}</span>
                        <div className="flex-1 min-w-0">
                          <div className={`font-bold text-sm truncate ${selectedLangCode === lang.code ? 'text-amber-400' : 'text-white'}`}>
                            {lang.name}
                          </div>
                          {lang.nativeName && lang.nativeName !== lang.name && (
                            <div className="text-stone-600 text-xs truncate">{lang.nativeName}</div>
                          )}
                        </div>
                        {selectedLangCode === lang.code && (
                          <CheckCircle2 size={14} className="text-amber-500 flex-shrink-0" />
                        )}
                      </button>
                    ))
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Accent selector */}
      <div className="space-y-2">
        <label className="text-xs font-black text-stone-400 uppercase tracking-widest flex items-center gap-1.5">
          <Mic2 size={12} />
          Accent / Dialect
        </label>
        <div className="grid grid-cols-1 gap-2 max-h-48 overflow-y-auto scrollbar-hide pr-1">
          {accentOptions.map((accent) => (
            <button
              key={accent.id}
              onClick={() => setSelectedAccentId(accent.id)}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-all ${
                selectedAccentId === accent.id
                  ? 'bg-amber-500/15 border-amber-500/40 text-white'
                  : 'bg-stone-900/40 border-white/8 text-stone-400 hover:bg-white/5 hover:border-white/15 hover:text-stone-200'
              }`}
            >
              <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${
                selectedAccentId === accent.id ? 'border-amber-500 bg-amber-500' : 'border-stone-600'
              }`}>
                {selectedAccentId === accent.id && (
                  <div className="w-1.5 h-1.5 bg-black rounded-full" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-bold text-sm">{accent.label}</div>
                {accent.description && (
                  <div className="text-stone-600 text-xs">{accent.description}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Subtitle Style Aesthetic Preset Selector (if captionStyle provided) */}
      {captionStyle && onCaptionStyleChange && (
        <div className="space-y-2 pt-2 border-t border-white/10">
          <div className="flex items-center justify-between">
            <label className="text-xs font-black text-stone-400 uppercase tracking-widest flex items-center gap-1.5">
              <Sparkles size={12} className="text-amber-400" />
              Subtitle Aesthetic Preset
            </label>
            <span className="text-[10px] text-amber-500 font-semibold tracking-wide">
              Subtitles Sized Accurately (13pt)
            </span>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {CAPTION_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => onCaptionStyleChange(preset.config)}
                className={`flex flex-col items-center p-2 rounded-xl border text-center transition-all ${
                  captionStyle.preset === preset.id
                    ? 'bg-amber-500/20 border-amber-500 text-white shadow-sm shadow-amber-500/20 scale-[1.02]'
                    : 'bg-stone-900/60 border-white/10 text-stone-400 hover:border-white/20 hover:text-white'
                }`}
              >
                <div
                  className="w-4 h-4 rounded-full border border-black/40 mb-1"
                  style={{ backgroundColor: preset.textColor }}
                />
                <span className="text-[10px] font-bold truncate max-w-full">{preset.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* CTA */}
      <Button
        onClick={() => onConfirm(selectedLangCode, selectedAccentId)}
        disabled={isConfirming}
        className="w-full h-14 bg-white hover:bg-amber-500 text-black font-black text-lg rounded-2xl shadow-lg transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-40 disabled:hover:scale-100"
      >
        {isConfirming ? (
          <>
            <Loader2 className="animate-spin mr-2" size={20} />
            Starting Transcription...
          </>
        ) : (
          <>
            <CheckCircle2 className="mr-2" size={20} />
            Start Transcribing
          </>
        )}
      </Button>

      <p className="text-center text-stone-600 text-[10px] font-bold uppercase tracking-widest">
        Powered by Whisper large-v3 — 99 languages · All accents
      </p>
    </motion.div>
  );
}
