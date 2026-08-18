import React, { useState, useEffect } from 'react';
import { CheckCircle2, Zap, TrendingUp, Award } from 'lucide-react';
import { clsx } from 'clsx';
import { apiFetch } from '../lib/api';

interface RehabPlan {
  planId: string;
  name: string;
  description: string;
  difficulty: string;
  durationWeeks: number;
  exercises: Array<{
    name: string;
    targetReps: number;
    targetSets: number;
    restSeconds: number;
    notes: string;
    order: number;
  }>;
}

interface PlanSelectorProps {
  onPlanSelected: (plan: RehabPlan) => void;
  isOpen: boolean;
}

export default function PlanSelector({ onPlanSelected, isOpen }: PlanSelectorProps) {
  const [plans, setPlans] = useState<RehabPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    // Load rehabilitation plans
    const loadPlans = async () => {
      try {
        const response = await apiFetch('/api/rehabilitation-plans');
        if (!response.ok) throw new Error('Unable to load rehabilitation plans');
        const data = await response.json();
        setPlans(data.plans);
        if (data.plans.length > 0) {
          setSelectedPlanId(data.plans[0].planId);
        }
      } catch (error) {
        console.error('Failed to load plans:', error);
        setError(error instanceof Error ? error.message : 'Unable to load plans');
      } finally {
        setLoading(false);
      }
    };

    loadPlans();
  }, []);

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case 'beginner':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'intermediate':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'advanced':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const getDifficultyIcon = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case 'beginner':
        return <CheckCircle2 className="w-4 h-4" />;
      case 'intermediate':
        return <Zap className="w-4 h-4" />;
      case 'advanced':
        return <TrendingUp className="w-4 h-4" />;
      default:
        return <Award className="w-4 h-4" />;
    }
  };

  const selectedPlan = plans.find(p => p.planId === selectedPlanId);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-950 border border-white/10 rounded-3xl max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gray-950 border-b border-white/10 p-6 z-10">
          <h2 className="text-3xl font-bold text-white mb-2">Select Your Recovery Plan</h2>
          <p className="text-gray-400">Choose a plan tailored to your recovery needs</p>
        </div>

        {loading ? (
          <div className="p-12 flex items-center justify-center">
            <div className="text-gray-400">Loading plans...</div>
          </div>
        ) : error ? (
          <div className="p-12 text-center text-red-400">{error}</div>
        ) : (
          <div className="p-6 grid md:grid-cols-2 gap-6">
            {/* Plans List */}
            <div className="space-y-3">
              {plans.map((plan) => (
                <button
                  key={plan.planId}
                  onClick={() => setSelectedPlanId(plan.planId)}
                  className={clsx(
                    "w-full p-4 rounded-xl border-2 transition-all text-left",
                    selectedPlanId === plan.planId
                      ? "border-neon-cyan bg-neon-cyan/10"
                      : "border-white/10 bg-gray-900/50 hover:border-white/20"
                  )}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-bold text-white mb-1">{plan.name}</h3>
                      <p className="text-sm text-gray-400">{plan.durationWeeks} weeks</p>
                    </div>
                    <div className={clsx("px-2 py-1 rounded border text-xs font-medium flex items-center gap-1", getDifficultyColor(plan.difficulty))}>
                      {getDifficultyIcon(plan.difficulty)}
                      {plan.difficulty}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Plan Details */}
            {selectedPlan && (
              <div className="bg-gray-900 border border-white/10 rounded-2xl p-6">
                <h3 className="text-2xl font-bold text-white mb-2">{selectedPlan.name}</h3>
                <p className="text-gray-400 mb-6">{selectedPlan.description}</p>

                {/* Plan Info */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">Duration</div>
                    <div className="text-lg font-bold text-white">{selectedPlan.durationWeeks} Weeks</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">Exercises</div>
                    <div className="text-lg font-bold text-white">{selectedPlan.exercises.length}</div>
                  </div>
                </div>

                {/* Exercises List */}
                <div>
                  <h4 className="text-sm font-bold uppercase text-gray-400 mb-3 tracking-wider">Exercises in Plan</h4>
                  <div className="space-y-2">
                    {selectedPlan.exercises.map((exercise, idx) => (
                      <div
                        key={idx}
                        className="bg-gray-800/50 border border-white/5 rounded-lg p-3"
                      >
                        <div className="flex items-start justify-between mb-1">
                          <h5 className="font-semibold text-white">{exercise.order}. {exercise.name}</h5>
                          <span className="text-xs text-neon-cyan font-mono">
                            {exercise.targetReps}×{exercise.targetSets}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400">{exercise.notes}</p>
                        <div className="text-xs text-gray-500 mt-1">
                          Rest: {exercise.restSeconds}s between sets
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Start Button */}
                <button
                  onClick={() => onPlanSelected(selectedPlan)}
                  className="w-full mt-8 px-6 py-4 bg-white text-black rounded-full font-bold text-lg hover:bg-gray-200 transition-colors flex items-center justify-center gap-2 group"
                >
                  <span>Start This Plan</span>
                  <span className="group-hover:translate-x-1 transition-transform">→</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
