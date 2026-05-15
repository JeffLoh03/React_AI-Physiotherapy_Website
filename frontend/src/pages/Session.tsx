import React, { useRef, useState, useEffect, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Link } from 'react-router-dom';
import { ArrowLeft, Play, Square, Flag, Download, X } from 'lucide-react';
import { jsPDF } from 'jspdf';
import CameraPanel from '../components/CameraPanel';
import FeedbackPanel from '../components/FeedbackPanel';
import { captureFrame } from '../lib/frame';

const WS_URL = (import.meta.env.VITE_WS_URL as string) || 'ws://localhost:8000/ws';

interface SessionSummary {
  date: string;
  durationSeconds: number;
  totalReps: number;
  mostFrequentExercise: string;
  message: string;
}

export default function Session() {
  const webcamRef = useRef<Webcam>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameIntervalRef = useRef<number | null>(null);

  const [isActive, setIsActive] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [summaryData, setSummaryData] = useState<SessionSummary | null>(null);

  const [metrics, setMetrics] = useState({
    detectedExerciseLabel: "None",
    confidenceScore: 0,
    angleValue: 0,
    angleError: 0,
    feedbackText: "Ready",
    repCount: 0
  });

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log("WS Connected");
      setIsConnected(true);
    };

    ws.onclose = () => {
      console.log("WS Disconnected");
      setIsConnected(false);
      setIsActive(false);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.summary) {
          setSummaryData(data.summary);
          setShowSummary(true);
          setIsActive(false);
          return;
        }

        setMetrics({
          detectedExerciseLabel: data.detectedExerciseLabel || "None",
          confidenceScore: data.confidenceScore || 0,
          angleValue: data.angleValue ?? 0,
          angleError: data.angleError ?? 0,
          feedbackText: data.feedbackText || "No pose",
          repCount: data.repCount ?? 0
        });
      } catch (e) {
        console.error("Parse error", e);
      }
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    };
  }, [connectWebSocket]);

  const sendCommand = (cmd: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: cmd }));
    }
  };

  const startSession = () => {
    if (!isConnected) connectWebSocket();
    sendCommand("START_SESSION");
    setIsActive(true);
    setShowSummary(false);
  };

  const stopSession = () => {
    setIsActive(false);
    setMetrics(prev => ({ ...prev, feedbackText: "Paused" }));
  };

  const endSession = () => {
    sendCommand("END_SESSION");
    setIsActive(false);
  };

  const downloadSummary = () => {
    if (!summaryData) return;

    try {
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      });

      // Add background
      pdf.setFillColor(30, 30, 30);
      pdf.rect(0, 0, 210, 297, 'F');

      // Title
      pdf.setTextColor(0, 255, 255);
      pdf.setFontSize(24);
      pdf.text('Session Report', 105, 25, { align: 'center' });

      // Date
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(10);
      pdf.text(summaryData.date, 105, 35, { align: 'center' });

      // Separator line
      pdf.setDrawColor(0, 255, 255);
      pdf.line(20, 42, 190, 42);

      // Stats section
      pdf.setFontSize(12);
      pdf.setTextColor(0, 255, 255);
      pdf.text('Performance Metrics:', 20, 55);

      // Stats items
      const stats = [
        { label: 'Duration', value: `${summaryData.durationSeconds} seconds` },
        { label: 'Total Reps', value: String(summaryData.totalReps) },
        { label: 'Top Exercise', value: summaryData.mostFrequentExercise },
      ];

      let yPos = 68;
      pdf.setFontSize(11);
      
      stats.forEach((stat) => {
        pdf.setTextColor(255, 255, 255);
        pdf.text(`${stat.label}:`, 25, yPos);
        pdf.setTextColor(0, 255, 255);
        pdf.text(stat.value, 170, yPos, { align: 'right' });
        yPos += 10;
      });

      // Message section
      pdf.line(20, yPos + 3, 190, yPos + 3);
      yPos += 15;
      pdf.setTextColor(0, 255, 255);
      pdf.setFontSize(12);
      pdf.text('Feedback:', 20, yPos);
      
      pdf.setFontSize(11);
      pdf.setTextColor(255, 255, 255);
      const messageLines = pdf.splitTextToSize(summaryData.message, 160);
      pdf.text(messageLines, 20, yPos + 8);

      // Footer
      pdf.setFontSize(9);
      pdf.setTextColor(150, 150, 150);
      pdf.text(`Generated: ${new Date().toLocaleString()}`, 105, 285, { align: 'center' });

      // Save PDF
      pdf.save(`session-summary-${Date.now()}.pdf`);
    } catch (error) {
      console.error('PDF generation error:', error);
      alert('Failed to generate PDF. Please try again.');
    }
  };

  // Frame Loop
  useEffect(() => {
    if (isActive && isConnected) {
      frameIntervalRef.current = window.setInterval(() => {
        if (webcamRef.current && webcamRef.current.video && wsRef.current?.readyState === WebSocket.OPEN) {
          const frameBase64 = captureFrame(webcamRef.current.video);
          if (frameBase64) {
            wsRef.current.send(JSON.stringify({
              frame: frameBase64,
              timestamp: Date.now()
            }));
          }
        }
      }, 100);
    } else {
      if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    }
    return () => {
      if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    };
  }, [isActive, isConnected]);

  return (
    <div className="min-h-screen p-4 md:p-8 flex flex-col relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <Link to="/" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
          <ArrowLeft className="w-5 h-5" />
          <span className="font-mono text-sm">HOME</span>
        </Link>
        <div className="font-bold text-xl tracking-wider">
          LIVE <span className="text-neon-cyan">SESSION</span>
        </div>
        <div className="w-24"></div>
      </div>

      {/* Main Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl mx-auto w-full">
        {/* Camera */}
        <div className="lg:col-span-2 h-[500px] lg:h-auto min-h-[400px]">
          <CameraPanel 
            ref={webcamRef} 
            onUserMedia={() => console.log("Cam OK")}
          />
        </div>

        {/* Controls & Feedback */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          {/* Controls */}
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={startSession}
              disabled={isActive}
              className={`flex flex-col items-center justify-center p-3 rounded-xl font-bold transition-all ${isActive ? 'bg-gray-800 text-gray-500' : 'bg-white text-black hover:bg-neon-cyan'}`}
            >
              <Play className="w-5 h-5 mb-1" /> START
            </button>
            <button
              onClick={stopSession}
              disabled={!isActive}
              className={`flex flex-col items-center justify-center p-3 rounded-xl font-bold transition-all ${!isActive ? 'bg-gray-800 text-gray-500' : 'bg-yellow-500 text-black hover:bg-yellow-400'}`}
            >
              <Square className="w-5 h-5 mb-1 fill-current" /> PAUSE
            </button>
            <button
              onClick={endSession}
              className="flex flex-col items-center justify-center p-3 rounded-xl font-bold bg-red-500 text-white hover:bg-red-600 transition-all"
            >
              <Flag className="w-5 h-5 mb-1" /> END
            </button>
          </div>

          <div className="flex-1">
            <FeedbackPanel 
              isConnected={isConnected}
              detectedExerciseLabel={metrics.detectedExerciseLabel}
              confidenceScore={metrics.confidenceScore}
              angleValue={metrics.angleValue}
              angleError={metrics.angleError}
              feedbackText={metrics.feedbackText}
              repCount={metrics.repCount}
              onReconnect={connectWebSocket}
            />
          </div>
        </div>
      </div>

      {/* Summary Modal */}
      {showSummary && summaryData && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm p-4">
          <div className="bg-gray-900 border border-neon-purple rounded-2xl p-8 max-w-md w-full shadow-2xl relative">
            <button 
              onClick={() => setShowSummary(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>
            
            <h2 className="text-3xl font-bold text-white mb-2">Session Complete</h2>
            <p className="text-neon-cyan mb-6">{summaryData.message}</p>
            
            <div className="space-y-4 mb-8">
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-gray-400">Duration</span>
                <span className="font-mono">{summaryData.durationSeconds}s</span>
              </div>
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-gray-400">Total Reps</span>
                <span className="font-mono text-xl font-bold">{summaryData.totalReps}</span>
              </div>
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-gray-400">Top Exercise</span>
                <span className="font-mono text-neon-purple">{summaryData.mostFrequentExercise}</span>
              </div>
            </div>

            <button
              onClick={downloadSummary}
              className="w-full py-4 bg-white text-black rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-neon-cyan transition-colors"
            >
              <Download className="w-5 h-5" /> Download Report (PDF)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
