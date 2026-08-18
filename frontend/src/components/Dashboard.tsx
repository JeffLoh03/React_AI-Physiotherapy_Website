import React, { useState } from 'react';
import { ChevronDown, ChevronUp, AlertCircle, CheckCircle2, Clock, TrendingUp, Zap } from 'lucide-react';
import { clsx } from 'clsx';

interface Exercise {
  name: string;
  targetReps: number;
  targetSets: number;
  restSeconds: number;
  notes: string;
  order: number;
}

interface DashboardProps {
  planName: string;
  planExercises: Exercise[];
  currentExercise: string;
  currentSet: number;
  targetSets: number;
  repsInSet: number;
  targetReps: number;
  formQuality: number;
  speedWarning: string | null;
  sessionDuration: number;
  totalRepsCompleted: number;
  goodFormReps: number;
  averageAngle: number;
  angleConsistency: number;
  movementSpeed: string;
}

export default function Dashboard({
  planName,
  planExercises,
  currentExercise,
  currentSet,
  targetSets,
  repsInSet,
  targetReps,
  formQuality,
  speedWarning,
  sessionDuration,
  totalRepsCompleted,
  goodFormReps,
  averageAngle,
  angleConsistency,
  movementSpeed,
}: DashboardProps) {
  const [expandedSections, setExpandedSections] = useState({
    formQuality: true,
    sessionStats: false,
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const setProgress = Math.min(100, Math.max(0, (repsInSet / Math.max(targetReps, 1)) * 100));

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const speedColor = speedWarning === 'TOO_FAST' ? 'text-red-500' : speedWarning === 'SLOW_DOWN' ? 'text-yellow-500' : 'text-green-500';
  const speedBgColor = speedWarning === 'TOO_FAST' ? 'bg-red-500/20 border-red-500/30' : speedWarning === 'SLOW_DOWN' ? 'bg-yellow-500/20 border-yellow-500/30' : 'bg-green-500/20 border-green-500/30';

  return (
    <div className="w-full h-full flex flex-col gap-4 p-4 bg-gradient-to-b from-gray-950 to-black rounded-2xl border border-white/5 overflow-y-auto">
      {/* === CORE SECTION 1: Current Exercise === */}
      <div className="bg-gray-900/80 border border-neon-cyan/30 rounded-xl p-4">
        <h3 className="text-xs uppercase tracking-widest text-gray-400 mb-3">Active Exercise</h3>
        <div className="mb-3">
          <div className="text-2xl font-bold text-white mb-1">{currentExercise || 'Waiting...'}</div>
          <div className="text-xs text-gray-400">Set {currentSet}/{targetSets}</div>
        </div>

        {/* Rep Progress */}
        <div className="mb-3">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-semibold text-white">{repsInSet}/{targetReps} reps</span>
            <span className="text-xs text-gray-400">{Math.round(setProgress)}%</span>
          </div>
          <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-neon-cyan to-neon-purple transition-all duration-300"
              style={{ width: `${setProgress}%` }}
            />
          </div>
        </div>

        {/* Form Quality Badge */}
        <div className={clsx(
          "text-sm font-semibold px-3 py-1 rounded-full border inline-flex items-center gap-2",
          formQuality >= 80 ? "bg-green-500/20 text-green-400 border-green-500/30" : "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
        )}>
          <CheckCircle2 className="w-3 h-3" />
          Quality: {Math.round(formQuality)}%
        </div>
      </div>

      {/* === CORE SECTION 2: Speed Alert === */}
      <div className={clsx(
        "border rounded-xl p-4 flex items-start gap-3",
        speedBgColor
      )}>
        <AlertCircle className={clsx("w-5 h-5 flex-shrink-0 mt-0.5", speedColor)} />
        <div>
          <div className={clsx("font-bold text-sm", speedColor)}>
            {speedWarning === 'TOO_FAST' && '🔴 TOO FAST - Pause and reset!'}
            {speedWarning === 'SLOW_DOWN' && '⚠️ Slow down - Maintain control'}
            {!speedWarning && '✓ Movement speed: NORMAL'}
          </div>
          <div className="text-xs text-gray-300 mt-1">
            {speedWarning === 'TOO_FAST' && 'You\'re moving too quickly. Slow down for safety and form quality.'}
            {speedWarning === 'SLOW_DOWN' && 'Reduce your pace slightly and keep the movement controlled.'}
            {!speedWarning && 'You\'re maintaining a good, controlled pace.'}
          </div>
        </div>
      </div>

      {/* === CORE SECTION 3: Plan Progress === */}
      <div className="bg-gray-900/50 border border-white/10 rounded-xl p-4">
        <h4 className="text-xs uppercase tracking-widest text-gray-400 mb-3">Plan Progress</h4>
        <div className="text-sm font-semibold text-white mb-3">{planName}</div>

        <div className="space-y-2 max-h-32 overflow-y-auto">
          {planExercises.map((ex, idx) => {
            const isCompleted = idx < planExercises.indexOf(
              planExercises.find(e => e.name === currentExercise) || planExercises[0]
            );
            const isCurrent = ex.name === currentExercise;

            return (
              <div
                key={idx}
                className={clsx(
                  "flex items-center gap-2 p-2 rounded",
                  isCurrent ? "bg-neon-cyan/20" : isCompleted ? "bg-green-500/20" : "bg-gray-800/30"
                )}
              >
                <div className={clsx("w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold",
                  isCurrent ? "bg-neon-cyan text-black" : isCompleted ? "bg-green-500 text-white" : "bg-gray-700 text-gray-400"
                )}>
                  {isCompleted ? "✓" : isCurrent ? "●" : idx + 1}
                </div>
                <div className="flex-1">
                  <div className="text-xs font-semibold text-white">{ex.name}</div>
                  <div className="text-xs text-gray-500">{ex.targetReps}×{ex.targetSets}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* === OPTIONAL SECTION 4: Form Quality (Collapsible) === */}
      <button
        onClick={() => toggleSection('formQuality')}
        className="w-full flex items-center justify-between bg-gray-900/50 border border-white/10 rounded-xl p-4 hover:border-white/20 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-neon-purple" />
          <span className="text-sm font-semibold text-white">Form Quality</span>
        </div>
        {expandedSections.formQuality ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expandedSections.formQuality && (
        <div className="bg-gray-900/50 border border-white/10 rounded-xl p-4 -mt-3 pt-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">Avg Angle</div>
              <div className="text-lg font-bold text-white">{Math.round(averageAngle)}°</div>
            </div>
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">Consistency</div>
              <div className="text-lg font-bold text-white">{Math.round(angleConsistency)}%</div>
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-2">Good Form Reps</div>
            <div className="text-sm font-semibold text-white">
              {goodFormReps}/{totalRepsCompleted} ({Math.round((goodFormReps / Math.max(totalRepsCompleted, 1)) * 100)}%)
            </div>
          </div>
        </div>
      )}

      {/* === OPTIONAL SECTION 5: Session Stats (Collapsible) === */}
      <button
        onClick={() => toggleSection('sessionStats')}
        className="w-full flex items-center justify-between bg-gray-900/50 border border-white/10 rounded-xl p-4 hover:border-white/20 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-neon-cyan" />
          <span className="text-sm font-semibold text-white">Session Stats</span>
        </div>
        {expandedSections.sessionStats ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expandedSections.sessionStats && (
        <div className="bg-gray-900/50 border border-white/10 rounded-xl p-4 -mt-3 pt-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">Duration</div>
              <div className="text-lg font-bold text-white font-mono">{formatDuration(sessionDuration)}</div>
            </div>
            <div className="bg-gray-800/50 rounded p-2">
              <div className="text-xs text-gray-400">Total Reps</div>
              <div className="text-lg font-bold text-white">{totalRepsCompleted}</div>
            </div>
          </div>
          <div className="bg-gray-800/50 rounded p-2">
            <div className="text-xs text-gray-400 mb-1">Movement Speed</div>
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-400" />
              <span className="font-semibold text-white">{movementSpeed}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
