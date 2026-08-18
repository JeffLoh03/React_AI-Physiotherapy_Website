import React, { useRef, useState, useEffect, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Play, Square, Flag, Download, X } from 'lucide-react';
import { jsPDF } from 'jspdf';
import CameraPanel from '../components/CameraPanel';
import FeedbackPanel from '../components/FeedbackPanel';
import Dashboard from '../components/Dashboard';
import PlanSelector from '../components/PlanSelector';
import ExerciseSelector from '../components/ExerciseSelector';
import { captureFrame } from '../lib/frame';
import { apiFetch, authenticatedWebSocketUrl } from '../lib/api';

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

interface SessionSummary {
  date: string;
  durationSeconds: number;
  totalReps: number;
  mostFrequentExercise: string;
  message: string;
  formQuality?: number;
  speedWarningsCount?: number;
  sessionId?: string;
}

const exerciseIdentity = (name: string): string => {
  const label = name.toLowerCase();
  if (label.includes('hip abduction')) return 'hip_abduction';
  if (label.includes('v-w') || label.includes('vw')) return 'shoulder_vw';
  if (label.includes('push')) return 'inclined_pushup';
  if (label.includes('lunge')) return 'forward_lunge';
  if (label.includes('squat')) return 'squat';
  if (label.includes('shoulder')) return 'shoulder_abduction';
  return label.trim();
};

export default function Session() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedAssignmentId = searchParams.get('assignment');
  const webcamRef = useRef<Webcam>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameIntervalRef = useRef<number | null>(null);
  const sessionStartTimeRef = useRef<number>(Date.now());
  const repTotalsRef = useRef<Record<string, number>>({});
  const angleHistoryRef = useRef<number[]>([]);
  const completedExercisesRef = useRef<Set<string>>(new Set());
  const completedSetsHandledRef = useRef<Record<string, number>>({});
  const pendingStartRef = useRef(false);

  // Plan & Exercise Selection
  const [selectedPlan, setSelectedPlan] = useState<RehabPlan | null>(null);
  const [showPlanSelector, setShowPlanSelector] = useState(true);
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [assignmentLoading, setAssignmentLoading] = useState(Boolean(requestedAssignmentId));
  const [exerciseSelectorOpen, setExerciseSelectorOpen] = useState(false);
  const [plannedExercise, setPlannedExercise] = useState('');

  // Session State
  const [isActive, setIsActive] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [restRemaining, setRestRemaining] = useState(0);
  const [exerciseAfterRest, setExerciseAfterRest] = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const [summaryData, setSummaryData] = useState<SessionSummary | null>(null);

  // Metrics
  const [metrics, setMetrics] = useState({
    detectedExerciseLabel: "None",
    confidenceScore: 0,
    angleValue: 0,
    angleError: 0,
    feedbackText: "Ready",
    repCount: 0,
    speedWarning: null as string | null,
    formQuality: 100,
    goodFormReps: 0,
    repPhase: "waiting_start",
    measuredSide: "both",
    exerciseMatched: false,
  });

  // Dashboard Data
  const [dashboardData, setDashboardData] = useState({
    currentExercise: "Waiting...",
    currentSet: 1,
    repsInSet: 0,
    formQuality: 100,
    speedWarning: null as string | null,
    sessionDuration: 0,
    totalRepsCompleted: 0,
    goodFormReps: 0,
    averageAngle: 0,
    angleConsistency: 100,
    movementSpeed: "NORMAL",
  });

  useEffect(() => {
    if (!requestedAssignmentId) return;
    const loadAssignment = async () => {
      try {
        const response = await apiFetch('/api/patient/assignments?active_only=true');
        if (!response.ok) throw new Error('Unable to load prescribed plan');
        const data = await response.json();
        const assignment = data.assignments.find(
          (item: { assignment_id: string }) => item.assignment_id === requestedAssignmentId
        );
        if (!assignment) throw new Error('This assigned plan is no longer active');
        setSelectedPlan(assignment.plan);
        setPlannedExercise(assignment.plan.exercises[0]?.name || '');
        setAssignmentId(assignment.assignment_id);
        setShowPlanSelector(false);
      } catch (error) {
        alert(error instanceof Error ? error.message : 'Unable to load prescribed plan');
        setShowPlanSelector(true);
      } finally {
        setAssignmentLoading(false);
      }
    };
    loadAssignment();
  }, [requestedAssignmentId]);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(authenticatedWebSocketUrl());

    ws.onopen = () => {
      console.log("WS Connected");
      setIsConnected(true);
      if (pendingStartRef.current && selectedPlan) {
        ws.send(JSON.stringify({
          command: 'START_SESSION',
          selectedPlan: selectedPlan.planId,
          assignmentId,
        }));
        pendingStartRef.current = false;
        setHasStarted(true);
        setIsActive(true);
      }
    };

    ws.onclose = () => {
      console.log("WS Disconnected");
      setIsConnected(false);
      setIsActive(false);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.error) {
          setMetrics(prev => ({ ...prev, feedbackText: data.error }));
          return;
        }
        
        if (data.summary) {
          setSummaryData(data.summary);
          setShowSummary(true);
          setIsActive(false);
          return;
        }

        setMetrics(prev => ({
          detectedExerciseLabel: data.detectedExerciseLabel ?? prev.detectedExerciseLabel,
          confidenceScore: data.confidenceScore ?? prev.confidenceScore,
          angleValue: data.angleValue ?? prev.angleValue,
          angleError: data.angleError ?? prev.angleError,
          // Empty feedback means "keep showing the last useful instruction".
          feedbackText: data.feedbackText || prev.feedbackText,
          repCount: data.repCount ?? prev.repCount,
          speedWarning: data.speedWarning ?? null,
          formQuality: data.formQuality ?? prev.formQuality,
          goodFormReps: data.goodFormReps ?? prev.goodFormReps,
          repPhase: data.repPhase ?? prev.repPhase,
          measuredSide: data.measuredSide ?? prev.measuredSide,
          exerciseMatched: data.exerciseMatched ?? prev.exerciseMatched,
        }));

        // Update dashboard data
        const exerciseName = data.currentExercise || selectedPlan?.exercises[0]?.name || "Waiting...";
        if (data.currentExercise) setPlannedExercise(data.currentExercise);
        const targetExercise = selectedPlan?.exercises.find(
          e => exerciseIdentity(e.name) === exerciseIdentity(exerciseName)
        );
        const sessionDuration = Math.floor((Date.now() - sessionStartTimeRef.current) / 1000);
        const targetReps = data.targetReps || targetExercise?.targetReps || 15;
        const targetSets = data.targetSets || targetExercise?.targetSets || 3;
        const currentReps = data.repCount ?? 0;
        if (exerciseName !== "Waiting..." && exerciseName !== "Unknown") {
          repTotalsRef.current[exerciseName] = Math.max(repTotalsRef.current[exerciseName] || 0, currentReps);
        }
        const totalReps = Object.values(repTotalsRef.current).reduce((sum, value) => sum + value, 0);
        if (typeof data.angleValue === 'number' && data.angleValue > 0) {
          angleHistoryRef.current.push(data.angleValue);
          if (angleHistoryRef.current.length > 30) angleHistoryRef.current.shift();
        }
        const angles = angleHistoryRef.current;
        const meanAngle = angles.length ? angles.reduce((sum, value) => sum + value, 0) / angles.length : 0;
        const variance = angles.length
          ? angles.reduce((sum, value) => sum + Math.pow(value - meanAngle, 2), 0) / angles.length
          : 0;
        const consistency = Math.max(0, Math.min(100, 100 - Math.sqrt(variance)));

        setDashboardData({
          currentExercise: exerciseName,
          currentSet: Math.min(Math.floor(currentReps / targetReps) + 1, targetSets),
          repsInSet: currentReps === 0 ? 0 : (currentReps % targetReps || targetReps),
          formQuality: data.formQuality ?? 100,
          speedWarning: data.speedWarning || null,
          sessionDuration,
          totalRepsCompleted: totalReps,
          goodFormReps: data.goodFormReps ?? 0,
          averageAngle: data.angleValue ?? 0,
          angleConsistency: consistency,
          movementSpeed: data.speedWarning === "TOO_FAST" ? "TOO FAST" : data.speedWarning === "SLOW_DOWN" ? "CAUTION" : "NORMAL",
        });

        const completedSets = Math.min(Math.floor(currentReps / targetReps), targetSets);
        const exerciseId = exerciseIdentity(targetExercise?.name || exerciseName);
        const lastHandledSet = completedSetsHandledRef.current[exerciseId] || 0;
        const completedNewSet = completedSets > lastHandledSet;

        // Derive set completion from cumulative reps. This remains reliable even
        // when the exact WebSocket frame that completed a set was not rendered.
        if (completedNewSet && selectedPlan) {
          completedSetsHandledRef.current[exerciseId] = completedSets;
          const index = selectedPlan.exercises.findIndex(
            exercise => exerciseIdentity(exercise.name) === exerciseIdentity(exerciseName)
          );
          if (index < 0) return;
          const currentExercise = selectedPlan.exercises[index];
          let nextName = currentExercise.name;
          const exerciseComplete = currentReps >= targetReps * targetSets;
          if (exerciseComplete && !completedExercisesRef.current.has(exerciseId)) {
            completedExercisesRef.current.add(exerciseId);
            const nextExercise = selectedPlan.exercises[index + 1];
            if (!nextExercise) {
              ws.send(JSON.stringify({ command: 'END_SESSION' }));
              setIsActive(false);
              setHasStarted(false);
              return;
            }
            nextName = nextExercise.name;
          }
          ws.send(JSON.stringify({ command: 'PAUSE_SESSION' }));
          setIsActive(false);
          setExerciseAfterRest(nextName);
          setRestRemaining(currentExercise?.restSeconds || 30);
        }
      } catch (e) {
        console.error("Parse error", e);
      }
    };

    wsRef.current = ws;
  }, [assignmentId, selectedPlan]);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    };
  }, [connectWebSocket]);

  const sendCommand = (cmd: string, data: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: cmd, ...data }));
    }
  };

  useEffect(() => {
    if (!exerciseAfterRest) return;
    if (restRemaining <= 0) {
      if (exerciseIdentity(exerciseAfterRest) !== exerciseIdentity(plannedExercise)) {
        sendCommand('SELECT_EXERCISE', { exerciseName: exerciseAfterRest });
      }
      sendCommand('RESUME_SESSION');
      setExerciseAfterRest(null);
      setIsActive(true);
      return;
    }
    const timer = window.setTimeout(() => setRestRemaining(value => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [exerciseAfterRest, restRemaining, plannedExercise]);

  const handlePlanSelected = (plan: RehabPlan) => {
    setSelectedPlan(plan);
    setPlannedExercise(plan.exercises[0]?.name || '');
    setAssignmentId(null);
    setShowPlanSelector(false);
    sessionStartTimeRef.current = Date.now();
  };

  const handleExerciseChange = (exerciseName: string) => {
    sendCommand("SELECT_EXERCISE", { exerciseName });
    setPlannedExercise(exerciseName);
    completedSetsHandledRef.current[exerciseIdentity(exerciseName)] = 0;
    angleHistoryRef.current = [];
  };

  const startSession = () => {
    if (!selectedPlan) {
      alert("Please select a rehabilitation plan first");
      return;
    }
    if (!isConnected) {
      pendingStartRef.current = true;
      connectWebSocket();
      setMetrics(prev => ({ ...prev, feedbackText: "Connecting..." }));
      return;
    }

    if (hasStarted) {
      sendCommand("RESUME_SESSION");
    } else {
      sendCommand("START_SESSION", {
        selectedPlan: selectedPlan.planId,
        assignmentId,
      });
      setHasStarted(true);
      repTotalsRef.current = {};
      completedExercisesRef.current = new Set();
      completedSetsHandledRef.current = {};
      angleHistoryRef.current = [];
    }
    setIsActive(true);
    setShowSummary(false);
    sessionStartTimeRef.current = Date.now();
  };

  const stopSession = () => {
    sendCommand("PAUSE_SESSION");
    setIsActive(false);
    setMetrics(prev => ({ ...prev, feedbackText: "Paused" }));
  };

  const endSession = () => {
    sendCommand("END_SESSION");
    setIsActive(false);
    setHasStarted(false);
  };

  const backToDashboard = () => {
    setShowSummary(false);
    navigate('/patient-dashboard', { replace: true });
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
      pdf.text('re+active Session Report', 105, 25, { align: 'center' });

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
        { label: 'Average Form', value: `${Math.round(summaryData.formQuality ?? 100)}%` },
        { label: 'Speed Warnings', value: String(summaryData.speedWarningsCount ?? 0) },
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
      pdf.text(`Generated by re+active • ${new Date().toLocaleString()}`, 105, 285, { align: 'center' });

      // Save PDF
      pdf.save(`re-active-session-${Date.now()}.pdf`);
      backToDashboard();
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

  // Show plan selector if no plan selected
  if (assignmentLoading) {
    return <div className="min-h-screen bg-black flex items-center justify-center text-white">Loading prescribed plan...</div>;
  }

  if (showPlanSelector) {
    return (
      <PlanSelector
        isOpen={true}
        onPlanSelected={handlePlanSelected}
      />
    );
  }

  // Main session layout
  return (
    <div className="min-h-screen p-4 md:p-8 flex flex-col relative bg-black">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Link
            to="/patient-dashboard"
            onClick={() => setShowPlanSelector(true)}
            className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="font-mono text-sm">BACK</span>
          </Link>
        </div>
        <div className="text-center">
          <div className="font-bold text-lg tracking-wider">
            <span className="text-white">re</span><span className="text-neon-cyan">+</span><span className="text-white">active</span>
          </div>
          {selectedPlan && <div className="text-xs text-gray-500">{selectedPlan.name}</div>}
        </div>
        <div className="w-24"></div>
      </div>

      {/* Main Grid - Camera, Feedback, Dashboard */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-[1600px] mx-auto w-full">
        {/* Enlarged primary camera workspace */}
        <div className="lg:col-span-7 h-[520px] lg:h-[65vh] min-h-[520px] max-h-[760px]">
          <CameraPanel 
            ref={webcamRef} 
            onUserMedia={() => console.log("Camera Ready")}
          />
        </div>

        {/* Feedback Panel */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          {/* Controls */}
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={startSession}
              disabled={isActive}
              className={`flex flex-col items-center justify-center p-3 rounded-xl font-bold text-xs transition-all ${isActive ? 'bg-gray-800 text-gray-500' : 'bg-white text-black hover:bg-neon-cyan'}`}
            >
              <Play className="w-4 h-4 mb-1" /> START
            </button>
            <button
              onClick={stopSession}
              disabled={!isActive}
              className={`flex flex-col items-center justify-center p-3 rounded-xl font-bold text-xs transition-all ${!isActive ? 'bg-gray-800 text-gray-500' : 'bg-yellow-500 text-black hover:bg-yellow-400'}`}
            >
              <Square className="w-4 h-4 mb-1 fill-current" /> PAUSE
            </button>
            <button
              onClick={endSession}
              className="flex flex-col items-center justify-center p-3 rounded-xl font-bold text-xs bg-red-500 text-white hover:bg-red-600 transition-all"
            >
              <Flag className="w-4 h-4 mb-1" /> END
            </button>
          </div>

          {/* Exercise Selector */}
          {selectedPlan && (
            <ExerciseSelector
              exercises={selectedPlan.exercises}
              currentExercise={plannedExercise || selectedPlan.exercises[0]?.name || "Select exercise"}
              onExerciseSelect={handleExerciseChange}
              isOpen={exerciseSelectorOpen}
              onToggle={() => setExerciseSelectorOpen(!exerciseSelectorOpen)}
            />
          )}

          {/* Feedback Panel */}
          <div className="flex-1 min-h-[300px]">
            <FeedbackPanel 
              isConnected={isConnected}
              detectedExerciseLabel={metrics.detectedExerciseLabel}
              confidenceScore={metrics.confidenceScore}
              angleValue={metrics.angleValue}
              angleError={metrics.angleError}
              feedbackText={metrics.feedbackText}
              repCount={metrics.repCount}
              repPhase={metrics.repPhase}
              measuredSide={metrics.measuredSide}
              exerciseMatched={metrics.exerciseMatched}
              onReconnect={connectWebSocket}
            />
          </div>
        </div>

        {/* Dashboard */}
        {selectedPlan && (
          <div className="lg:col-span-3">
            <Dashboard
              planName={selectedPlan.name}
              planExercises={selectedPlan.exercises}
              currentExercise={dashboardData.currentExercise}
              currentSet={dashboardData.currentSet}
              targetSets={selectedPlan.exercises.find(
                e => exerciseIdentity(e.name) === exerciseIdentity(dashboardData.currentExercise)
              )?.targetSets || 3}
              repsInSet={dashboardData.repsInSet}
              targetReps={selectedPlan.exercises.find(
                e => exerciseIdentity(e.name) === exerciseIdentity(dashboardData.currentExercise)
              )?.targetReps || 15}
              formQuality={dashboardData.formQuality}
              speedWarning={dashboardData.speedWarning}
              sessionDuration={dashboardData.sessionDuration}
              totalRepsCompleted={dashboardData.totalRepsCompleted}
              goodFormReps={dashboardData.goodFormReps}
              averageAngle={dashboardData.averageAngle}
              angleConsistency={dashboardData.angleConsistency}
              movementSpeed={dashboardData.movementSpeed}
            />
          </div>
        )}
      </div>

      {exerciseAfterRest && restRemaining > 0 && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-2xl border border-neon-cyan bg-gray-900 p-8 text-center">
            <p className="text-sm uppercase tracking-widest text-gray-400">Recovery timer</p>
            <p className="my-4 text-7xl font-bold text-neon-cyan">{restRemaining}</p>
            <p className="text-gray-300">Next: <span className="font-bold text-white">{exerciseAfterRest}</span></p>
            <button
              onClick={() => setRestRemaining(0)}
              className="mt-6 rounded-lg border border-white/20 px-5 py-2 text-sm text-white hover:bg-white/10"
            >
              Skip Rest
            </button>
          </div>
        </div>
      )}

      {/* Summary Modal */}
      {showSummary && summaryData && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm p-4">
          <div className="bg-gray-900 border border-neon-purple rounded-2xl p-8 max-w-md w-full shadow-2xl relative">
            <button 
              onClick={backToDashboard}
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
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-gray-400">Average Form</span>
                <span className="font-mono text-neon-cyan">{Math.round(summaryData.formQuality ?? 100)}%</span>
              </div>
              <div className="flex justify-between border-b border-white/10 pb-2">
                <span className="text-gray-400">Speed Warnings</span>
                <span className="font-mono">{summaryData.speedWarningsCount ?? 0}</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={downloadSummary}
                className="w-full py-4 bg-white text-black rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-neon-cyan transition-colors"
              >
                <Download className="w-5 h-5" /> Download PDF
              </button>
              <button
                onClick={backToDashboard}
                className="w-full py-4 border border-white/20 bg-white/5 text-white rounded-xl font-bold flex items-center justify-center gap-2 hover:border-neon-cyan hover:text-neon-cyan transition-colors"
              >
                <ArrowLeft className="w-5 h-5" /> Back to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
