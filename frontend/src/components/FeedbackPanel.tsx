import React from 'react';
import { Activity, RotateCcw, Trophy, Target } from 'lucide-react';
import { clsx } from 'clsx';

interface FeedbackPanelProps {
  isConnected: boolean;
  detectedExerciseLabel: string;
  confidenceScore: number;
  angleValue: number;
  angleError: number;
  feedbackText: string;
  repCount: number;
  repPhase: string;
  measuredSide: string;
  exerciseMatched: boolean;
  onReconnect: () => void;
}

export default function FeedbackPanel({
  isConnected,
  detectedExerciseLabel,
  confidenceScore,
  angleValue,
  angleError,
  feedbackText,
  repCount,
  repPhase,
  measuredSide,
  exerciseMatched,
  onReconnect
}: FeedbackPanelProps) {
  
  const isGood = exerciseMatched && Math.abs(angleError) <= 20;
  const confidencePercent = Math.round(confidenceScore * 100);

  let statusColor = "text-neon-cyan";
  let borderColor = "border-neon-cyan";
  
  if (!exerciseMatched) {
    statusColor = "text-yellow-400";
    borderColor = "border-yellow-500";
  } else if (!isGood) {
    statusColor = "text-neon-purple";
    borderColor = "border-neon-purple";
  }

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Connection Status */}
      <div className={clsx(
        "p-3 rounded-xl border flex items-center justify-between",
        isConnected ? "bg-green-900/20 border-green-500/30" : "bg-red-900/20 border-red-500/30"
      )}>
        <div className="flex items-center gap-2">
          <Activity className={clsx("w-4 h-4", isConnected ? "text-green-400" : "text-red-400")} />
          <span className="text-xs font-medium text-gray-300">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
        {!isConnected && (
          <button onClick={onReconnect} className="text-xs text-red-300 underline">Retry</button>
        )}
      </div>

      {/* Exercise Classification Card */}
      <div className="bg-gray-900/80 rounded-xl p-4 border border-white/10">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-gray-400 text-xs uppercase tracking-widest">Detected Exercise</h4>
          <span className={clsx("text-xs font-mono px-2 py-0.5 rounded", 
            confidencePercent > 80 ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400"
          )}>
            {confidencePercent}% CONFIDENCE
          </span>
        </div>
        <div className="text-xl font-bold text-white truncate">
          {detectedExerciseLabel || "Analyzing..."}
        </div>
      </div>

      {/* Main Feedback Card */}
      <div className={clsx(
        "flex-1 rounded-2xl border-2 p-6 flex flex-col items-center justify-center text-center transition-all duration-300 bg-black/40 backdrop-blur-sm",
        borderColor,
        isGood ? "bg-neon-cyan-glow" : "bg-neon-purple-glow"
      )}>
        <h3 className="text-gray-400 text-sm uppercase tracking-widest mb-2">Feedback</h3>
        
        <div className="text-3xl md:text-4xl font-bold mb-6 h-20 flex items-center justify-center leading-tight">
          <span className={statusColor}>{feedbackText || "Waiting..."}</span>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-3 w-full">
          <div className="bg-white/5 rounded-xl p-3 border border-white/10">
            <div className="text-gray-400 text-[10px] mb-1">ANGLE</div>
            <div className="text-xl font-mono font-bold">{angleValue.toFixed(0)}°</div>
          </div>
          
          <div className="bg-white/5 rounded-xl p-3 border border-white/10">
            <div className="text-gray-400 text-[10px] mb-1">ERROR</div>
            <div className={clsx("text-xl font-mono font-bold", statusColor)}>
              {angleError > 0 ? "+" : ""}{angleError.toFixed(0)}°
            </div>
          </div>
        </div>
        <div className="mt-3 text-[10px] uppercase tracking-wider text-gray-400">
          Phase: {repPhase.replace('_', ' ')} • Tracking: {measuredSide}
        </div>
      </div>

      {/* Rep Counter */}
      <div className="bg-gray-900 rounded-2xl p-5 border border-white/10 flex items-center justify-between">
        <div>
          <h4 className="text-gray-400 text-xs uppercase tracking-widest">Reps</h4>
          <div className="text-[10px] text-gray-500">SESSION TOTAL</div>
        </div>
        <div className="text-5xl font-bold text-white font-mono">
          {repCount}
        </div>
      </div>
    </div>
  );
}
