import React from 'react';
import { ChevronDown } from 'lucide-react';
import { clsx } from 'clsx';

interface Exercise {
  name: string;
  targetReps: number;
  targetSets: number;
  restSeconds: number;
  notes: string;
  order: number;
}

interface ExerciseSelectorProps {
  exercises: Exercise[];
  currentExercise: string;
  onExerciseSelect: (exercise: string) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export default function ExerciseSelector({
  exercises,
  currentExercise,
  onExerciseSelect,
  isOpen,
  onToggle,
}: ExerciseSelectorProps) {
  const current = exercises.find(e => e.name === currentExercise);

  return (
    <div className="relative w-full">
      {/* Selector Button */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-900 border border-neon-cyan/30 rounded-lg hover:border-neon-cyan/50 transition-colors text-left"
      >
        <div>
          <div className="text-xs text-gray-400 uppercase tracking-widest">Exercise</div>
          <div className="text-sm font-bold text-white">{currentExercise || 'Select exercise'}</div>
          {current && (
            <div className="text-xs text-gray-500 mt-1">
              {current.targetReps}×{current.targetSets} • {current.notes}
            </div>
          )}
        </div>
        <ChevronDown className={clsx("w-5 h-5 text-gray-400 transition-transform", isOpen && "rotate-180")} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-gray-900 border border-white/10 rounded-lg shadow-lg z-20">
          <div className="max-h-60 overflow-y-auto">
            {exercises.map((exercise) => (
              <button
                key={exercise.name}
                onClick={() => {
                  onExerciseSelect(exercise.name);
                  onToggle();
                }}
                className={clsx(
                  "w-full px-4 py-3 text-left border-b border-white/5 hover:bg-white/5 transition-colors last:border-b-0",
                  currentExercise === exercise.name && "bg-neon-cyan/10 border-l-2 border-l-neon-cyan"
                )}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm font-semibold text-white">{exercise.order}. {exercise.name}</div>
                    <div className="text-xs text-gray-400 mt-1">{exercise.notes}</div>
                  </div>
                  <div className="text-xs font-mono text-neon-cyan whitespace-nowrap ml-2">
                    {exercise.targetReps}×{exercise.targetSets}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
