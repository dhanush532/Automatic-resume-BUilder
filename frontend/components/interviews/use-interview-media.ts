"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type RecognitionResult = { isFinal: boolean; 0: { transcript: string } };
type Recognition = {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((event: { resultIndex: number; results: { length: number; [key: number]: RecognitionResult } }) => void) | null;
  onerror: ((event: { error: string }) => void) | null; onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
};
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };

export function useInterviewMedia(onTranscript: (text: string) => void) {
  const video = useRef<HTMLVideoElement>(null);
  const cameraStream = useRef<MediaStream | null>(null);
  const microphone = useRef<MediaStream | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const mounted = useRef(false);
  const cameraPending = useRef(false);
  const micPending = useRef(false);
  const generation = useRef(0);
  const transcriptCallback = useRef(onTranscript);
  transcriptCallback.current = onTranscript;
  const [camera, setCamera] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState("");
  const [speechSupported, setSpeechSupported] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);

  const stopMic = useCallback(() => {
    recognition.current?.abort(); recognition.current = null;
    microphone.current?.getTracks().forEach(track => track.stop()); microphone.current = null;
    setListening(false); setInterim("");
  }, []);
  const stopAll = useCallback(() => {
    generation.current++; stopMic();
    cameraStream.current?.getTracks().forEach(track => track.stop()); cameraStream.current = null;
    if (video.current) video.current.srcObject = null;
    window.speechSynthesis?.cancel();
    setCamera(false); setSpeaking(false);
  }, [stopMic]);
  useEffect(() => {
    mounted.current = true;
    const scope = window as SpeechWindow;
    setSpeechSupported(!!(scope.SpeechRecognition || scope.webkitSpeechRecognition));
    setVoiceSupported("speechSynthesis" in window);
    const visibility = () => { if (document.hidden) stopAll(); };
    document.addEventListener("visibilitychange", visibility);
    return () => { mounted.current = false; document.removeEventListener("visibilitychange", visibility); stopAll(); };
  }, [stopAll]);

  async function toggleCamera() {
    setError("");
    if (cameraStream.current) {
      cameraStream.current.getTracks().forEach(track => track.stop()); cameraStream.current = null;
      if (video.current) video.current.srcObject = null;
      setCamera(false); return;
    }
    if (cameraPending.current) return;
    if (!navigator.mediaDevices?.getUserMedia) { setError("Camera access needs HTTPS and a supported browser. You can continue with text."); return; }
    cameraPending.current = true;
    const requestGeneration = generation.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      if (!mounted.current || generation.current !== requestGeneration) { stream.getTracks().forEach(track => track.stop()); return; }
      cameraStream.current = stream;
      stream.getVideoTracks().forEach(track => { track.onended = () => { if (mounted.current) setCamera(false); cameraStream.current = null; }; });
      if (video.current) video.current.srcObject = stream;
      setCamera(true);
    } catch { if (mounted.current) setError("Camera unavailable or permission denied. Check browser permissions, or continue without video."); }
    finally { cameraPending.current = false; }
  }
  async function toggleMicrophone() {
    setError("");
    if (recognition.current) { recognition.current.stop(); return; }
    if (micPending.current) return;
    const scope = window as SpeechWindow;
    const Constructor = scope.SpeechRecognition || scope.webkitSpeechRecognition;
    if (!Constructor || !navigator.mediaDevices?.getUserMedia) { setError("Dictation is not supported here. Type your answer below; all interview features remain available."); return; }
    micPending.current = true;
    const requestGeneration = generation.current;
    try {
      window.speechSynthesis?.cancel(); setSpeaking(false);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      if (!mounted.current || generation.current !== requestGeneration) { stream.getTracks().forEach(track => track.stop()); return; }
      microphone.current = stream;
      const recognizer = new Constructor(); recognition.current = recognizer;
      recognizer.lang = "en-US"; recognizer.continuous = true; recognizer.interimResults = true;
      recognizer.onresult = event => {
        if (!mounted.current || recognition.current !== recognizer) return;
        let partial = "";
        for (let index = event.resultIndex; index < event.results.length; index++) {
          const result = event.results[index];
          if (result.isFinal) transcriptCallback.current(result[0].transcript);
          else partial += result[0].transcript;
        }
        setInterim(partial);
      };
      recognizer.onerror = event => {
        if (mounted.current) setError(`Dictation stopped (${event.error}). Your transcript is kept; you can type or retry.`);
        stopMic();
      };
      recognizer.onend = () => {
        if (recognition.current === recognizer) {
          recognition.current = null; microphone.current?.getTracks().forEach(track => track.stop()); microphone.current = null;
          if (mounted.current) { setListening(false); setInterim(""); }
        }
      };
      recognizer.start(); setListening(true);
    } catch { stopMic(); if (mounted.current) setError("Microphone unavailable or permission denied. Check browser permissions or type your answer."); }
    finally { micPending.current = false; }
  }
  function speak(text: string) {
    if (!window.speechSynthesis) { setError("Spoken questions are unavailable in this browser. Read the question on screen."); return; }
    stopMic(); window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text); utterance.lang = "en-US"; utterance.rate = .95;
    utterance.onstart = () => { if (mounted.current) setSpeaking(true); };
    utterance.onend = () => { if (mounted.current) setSpeaking(false); };
    utterance.onerror = () => { if (mounted.current) setSpeaking(false); };
    window.speechSynthesis.speak(utterance);
  }
  function stopSpeaking() { window.speechSynthesis?.cancel(); setSpeaking(false); }
  return { video, camera, listening, speaking, interim, error, speechSupported, voiceSupported, toggleCamera, toggleMicrophone, speak, stopSpeaking, stopAll };
}
