/**
 * audioExtractor.ts
 *
 * Client-side audio extraction using the Web Audio API.
 * Extracts the audio track from any video file (MP4, MOV, WebM, MKV) directly in the browser
 * and produces a lightweight 16kHz mono WAV (< 4 MB) for fast, seamless cloud transcription
 * on Vercel without hitting the 4.5 MB serverless payload ceiling.
 */

export function isCloudDeployment(): boolean {
  if (typeof window === 'undefined') return false;
  const host = window.location.hostname.toLowerCase();
  // If running on localhost or 127.0.0.1, it's the local / desktop environment
  if (host === 'localhost' || host === '127.0.0.1') return false;
  return true;
}

/**
 * Encodes an AudioBuffer into a standard 16kHz mono 16-bit PCM WAV Blob.
 */
function encodeMonoWav(buffer: AudioBuffer, targetSampleRate = 16000): Blob {
  const numChannels = 1;
  const sourceRate = buffer.sampleRate;

  // Mix down channels to mono
  let monoData: Float32Array;
  if (buffer.numberOfChannels > 1) {
    const ch0 = buffer.getChannelData(0);
    const ch1 = buffer.getChannelData(1);
    monoData = new Float32Array(buffer.length);
    for (let i = 0; i < buffer.length; i++) {
      monoData[i] = (ch0[i] + ch1[i]) / 2;
    }
  } else {
    monoData = buffer.getChannelData(0);
  }

  // Downsample to target sample rate (default 16kHz for Whisper)
  let samples: Float32Array;
  if (sourceRate !== targetSampleRate) {
    const ratio = sourceRate / targetSampleRate;
    const newLen = Math.round(monoData.length / ratio);
    samples = new Float32Array(newLen);
    for (let i = 0; i < newLen; i++) {
      samples[i] = monoData[Math.round(i * ratio)] || 0;
    }
  } else {
    samples = monoData;
  }

  // If even at 16kHz the WAV would exceed 4MB (~130 seconds),
  // adaptively downsample to 12kHz or 8kHz so it safely stays under 4.1MB
  let finalRate = targetSampleRate;
  if (samples.length * 2 > 4.1 * 1024 * 1024) {
    finalRate = 8000;
    const ratio = targetSampleRate / finalRate;
    const newLen = Math.round(samples.length / ratio);
    const compressed = new Float32Array(newLen);
    for (let i = 0; i < newLen; i++) {
      compressed[i] = samples[Math.round(i * ratio)] || 0;
    }
    samples = compressed;
  }

  const bitDepth = 16;
  const bytesPerSample = bitDepth / 8;
  const dataSize = samples.length * bytesPerSample;
  const headerSize = 44;
  const totalSize = headerSize + dataSize;

  const arrayBuffer = new ArrayBuffer(totalSize);
  const view = new DataView(arrayBuffer);

  function writeString(offset: number, str: string) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  // RIFF chunk descriptor
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, 'WAVE');

  // fmt sub-chunk
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size
  view.setUint16(20, 1, true); // AudioFormat (1 = PCM)
  view.setUint16(22, numChannels, true); // NumChannels
  view.setUint32(24, finalRate, true); // SampleRate
  view.setUint32(28, finalRate * numChannels * bytesPerSample, true); // ByteRate
  view.setUint16(32, numChannels * bytesPerSample, true); // BlockAlign
  view.setUint16(34, bitDepth, true); // BitsPerSample

  // data sub-chunk
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  // PCM samples
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    const val = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(offset, val, true);
    offset += 2;
  }

  return new Blob([arrayBuffer], { type: 'audio/wav' });
}

/**
 * Extracts and optimizes audio from a video file in the browser.
 */
export async function extractAudioFromVideo(
  videoFile: File,
  onProgress?: (message: string) => void
): Promise<File> {
  onProgress?.('Reading video file in browser...');
  let arrayBuffer: ArrayBuffer;
  try {
    arrayBuffer = await videoFile.arrayBuffer();
  } catch (readErr: any) {
    throw new Error(
      `Browser could not read the video file directly: ${readErr?.message || 'File access locked'}. ` +
      `Please ensure the video is not open in another player, or use the Verbum desktop software.`
    );
  }

  const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
  if (!AudioCtx) {
    throw new Error('Web Audio API is not supported in this browser.');
  }

  const audioCtx = new AudioCtx();
  try {
    onProgress?.('Decoding audio data...');
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

    onProgress?.('Optimizing audio for cloud transcription...');
    const wavBlob = encodeMonoWav(audioBuffer, 16000);

    const baseName = videoFile.name.replace(/\.[^/.]+$/, '');
    return new File([wavBlob], `${baseName}.wav`, { type: 'audio/wav' });
  } catch (decodeErr: any) {
    throw new Error(
      `Audio decoding error in browser: ${decodeErr?.message || 'Video container format not supported'}. ` +
      `For direct multi-format video transcription, run the Verbum desktop application.`
    );
  } finally {
    try {
      audioCtx.close();
    } catch {}
  }
}
