import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, Search, BarChart3, ClipboardPlus, TrendingUp, UserPlus, Zap, Users, Trash2 } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { apiFetch, clearAuth } from '../lib/api';
import { buildDailyActivity } from '../lib/dailyActivity';

interface PatientData {
  profile: {
    user_id: string;
    username: string;
    total_xp: number;
    current_streak: number;
    total_sessions: number;
    best_form_quality: number;
  };
  sessions: Array<{
    date: string;
    duration: number;
    exercise_name: string;
    total_reps: number;
    form_quality: number;
    xp_earned: number;
  }>;
  total_reps_all_time: number;
  avg_form_quality: number;
  assignments: Array<{
    assignment_id: string;
    status: string;
    completed_sessions: number;
    last_completed_at: string | null;
    assigned_at: string;
    plan: { name: string; durationWeeks: number };
  }>;
}

interface SearchResult {
  user_id: string;
  username: string;
  is_linked: boolean;
}

interface LinkedPatient {
  user_id: string;
  username: string;
  total_xp: number;
  current_streak: number;
  total_sessions: number;
  best_form_quality: number;
  created_at: string;
}

interface RehabPlan {
  planId: string;
  name: string;
}

export default function DoctorDashboard() {
  const navigate = useNavigate();
  const [searchUsername, setSearchUsername] = useState('');
  const [patientData, setPatientData] = useState<PatientData | null>(null);
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [linkedPatients, setLinkedPatients] = useState<LinkedPatient[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(true);
  const [removingPatientId, setRemovingPatientId] = useState<string | null>(null);
  const [plans, setPlans] = useState<RehabPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [assignmentNotes, setAssignmentNotes] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const username = localStorage.getItem('username');
  const userId = localStorage.getItem('user_id');

  const loadLinkedPatients = async () => {
    setPatientsLoading(true);
    try {
      const response = await apiFetch('/api/doctor/patients');
      if (!response.ok) throw new Error('Unable to load linked patients');
      const data = await response.json();
      setLinkedPatients(data.patients || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load linked patients');
    } finally {
      setPatientsLoading(false);
    }
  };

  useEffect(() => {
    void loadLinkedPatients();
    apiFetch('/api/rehabilitation-plans')
      .then(async response => {
        if (!response.ok) return;
        const data = await response.json();
        setPlans(data.plans || []);
        setSelectedPlanId(data.plans?.[0]?.planId || '');
      })
      .catch(console.error);
  }, []);

  if (!userId) {
    navigate('/auth');
    return null;
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await apiFetch(`/api/doctor/search-patient/${encodeURIComponent(searchUsername.trim())}`);

      if (!response.ok) {
        setError('Patient not found');
        setPatientData(null);
        setSearchResult(null);
        return;
      }

      const result: SearchResult = await response.json();
      setSearchResult(result);
      if (result.is_linked) await loadAnalytics(result.user_id);
      else setPatientData(null);
    } catch (err) {
      setError('Error searching patient');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadAnalytics = async (patientId: string) => {
    const analyticsRes = await apiFetch(`/api/doctor/patient-analytics/${patientId}?days=30`);
    if (!analyticsRes.ok) throw new Error('Unable to load patient analytics');
    setPatientData(await analyticsRes.json());
  };

  const selectLinkedPatient = async (patient: LinkedPatient) => {
    setLoading(true);
    setError('');
    setSuccess('');
    setSearchResult({
      user_id: patient.user_id,
      username: patient.username,
      is_linked: true,
    });
    try {
      await loadAnalytics(patient.user_id);
    } catch (err) {
      setPatientData(null);
      setError(err instanceof Error ? err.message : 'Unable to load patient analytics');
    } finally {
      setLoading(false);
    }
  };

  const linkPatient = async () => {
    if (!searchResult) return;
    setLoading(true);
    setError('');
    try {
      const response = await apiFetch(`/api/doctor/patients/${searchResult.user_id}`, { method: 'POST' });
      if (!response.ok) throw new Error('Unable to link patient');
      setSearchResult({ ...searchResult, is_linked: true });
      setSuccess('Patient linked to your care list.');
      await loadLinkedPatients();
      await loadAnalytics(searchResult.user_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to link patient');
    } finally {
      setLoading(false);
    }
  };

  const removeLinkedPatient = async (patient: LinkedPatient) => {
    const confirmed = window.confirm(
      `Remove ${patient.username} from your patient list? Their records will be kept, but your active plans for them will be paused.`
    );
    if (!confirmed) return;

    setRemovingPatientId(patient.user_id);
    setError('');
    setSuccess('');
    try {
      const response = await apiFetch(`/api/doctor/patients/${patient.user_id}`, {
        method: 'DELETE',
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to remove patient');
      setLinkedPatients(current => current.filter(item => item.user_id !== patient.user_id));
      if (searchResult?.user_id === patient.user_id) {
        setSearchResult(null);
        setPatientData(null);
      }
      setSuccess(`${patient.username} was removed from your patient list.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to remove patient');
    } finally {
      setRemovingPatientId(null);
    }
  };

  const assignPlan = async () => {
    if (!searchResult || !selectedPlanId) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const response = await apiFetch('/api/doctor/assignments', {
        method: 'POST',
        body: JSON.stringify({
          patient_id: searchResult.user_id,
          plan_id: selectedPlanId,
          notes: assignmentNotes,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to assign plan');
      setAssignmentNotes('');
      setSuccess(`${data.plan.name} assigned successfully.`);
      await loadAnalytics(searchResult.user_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to assign plan');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    clearAuth();
    navigate('/auth');
  };

  const chartData = buildDailyActivity(patientData?.sessions || [], 7);

  return (
    <div className="min-h-screen bg-black p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <img src="/image.png" alt="re+active" className="h-12 mb-2" />
            <h1 className="text-3xl font-bold text-white">
              Doctor Dashboard • <span className="text-neon-cyan">{username}</span>
            </h1>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors"
          >
            <LogOut size={20} /> Logout
          </button>
        </div>

        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)] lg:items-start">
          <aside className="rounded-xl border border-gray-800 bg-gray-900 p-4 lg:sticky lg:top-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="flex items-center gap-2 font-bold text-white">
                <Users size={20} className="text-neon-cyan" /> My Patients
              </h2>
              <span className="rounded-full bg-neon-cyan/10 px-2 py-0.5 text-xs text-neon-cyan">
                {linkedPatients.length}
              </span>
            </div>

            {patientsLoading ? (
              <p className="py-6 text-center text-sm text-gray-500">Loading patients...</p>
            ) : linkedPatients.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-700 p-4 text-center">
                <p className="text-sm text-gray-400">No linked patients yet.</p>
                <p className="mt-1 text-xs text-gray-600">Search by username to add one.</p>
              </div>
            ) : (
              <div className="max-h-[65vh] space-y-2 overflow-y-auto pr-1">
                {linkedPatients.map(patient => {
                  const selected = searchResult?.user_id === patient.user_id;
                  return (
                    <div
                      key={patient.user_id}
                      className={`flex items-center gap-2 rounded-lg border p-2 transition-colors ${
                        selected
                          ? 'border-neon-cyan bg-neon-cyan/10'
                          : 'border-white/10 bg-gray-800 hover:border-white/20'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => void selectLinkedPatient(patient)}
                        className="min-w-0 flex-1 px-1 py-1 text-left"
                      >
                        <p className="truncate font-semibold text-white">{patient.username}</p>
                        <p className="text-xs text-gray-500">
                          {patient.total_sessions} sessions • {patient.current_streak} day streak
                        </p>
                      </button>
                      <button
                        type="button"
                        onClick={() => void removeLinkedPatient(patient)}
                        disabled={removingPatientId === patient.user_id}
                        aria-label={`Remove ${patient.username}`}
                        title="Remove linked patient"
                        className="rounded-md p-2 text-gray-500 hover:bg-red-500/10 hover:text-red-400 disabled:opacity-40"
                      >
                        <Trash2 size={17} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </aside>

          <main className="min-w-0">

        {/* Search Section */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
          <h2 className="text-xl font-bold text-white mb-4">Search Patient</h2>
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={searchUsername}
              onChange={(e) => setSearchUsername(e.target.value)}
              placeholder="Enter patient username..."
              className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:border-neon-cyan focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-3 bg-neon-cyan text-black font-bold rounded-lg hover:bg-cyan-400 disabled:opacity-50 transition-all flex items-center gap-2"
            >
              <Search size={20} /> Search
            </button>
          </form>
          {error && <p className="text-red-400 mt-3">{error}</p>}
          {success && <p className="text-green-400 mt-3">{success}</p>}

          {searchResult && (
            <div className="mt-5 rounded-xl border border-white/10 bg-gray-800 p-4">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="font-bold text-white">{searchResult.username}</p>
                  <p className="text-sm text-gray-400">
                    {searchResult.is_linked ? 'Linked patient' : 'Not yet linked to your care list'}
                  </p>
                </div>
                {!searchResult.is_linked && (
                  <button
                    onClick={linkPatient}
                    disabled={loading}
                    className="flex items-center justify-center gap-2 rounded-lg bg-neon-cyan px-5 py-2.5 font-bold text-black disabled:opacity-50"
                  >
                    <UserPlus size={18} /> Add to My Patients
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {searchResult?.is_linked && (
          <div className="bg-gray-900 border border-neon-cyan/20 rounded-xl p-6 mb-8">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <ClipboardPlus className="text-neon-cyan" size={22} /> Assign Rehabilitation Plan
            </h2>
            <div className="grid gap-3 md:grid-cols-[1fr_2fr_auto]">
              <select
                value={selectedPlanId}
                onChange={event => setSelectedPlanId(event.target.value)}
                className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white focus:border-neon-cyan focus:outline-none"
              >
                {plans.map(plan => <option key={plan.planId} value={plan.planId}>{plan.name}</option>)}
              </select>
              <input
                value={assignmentNotes}
                onChange={event => setAssignmentNotes(event.target.value)}
                placeholder="Clinical notes or patient instructions"
                className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white focus:border-neon-cyan focus:outline-none"
              />
              <button
                onClick={assignPlan}
                disabled={loading || !selectedPlanId}
                className="rounded-lg bg-neon-cyan px-6 py-3 font-bold text-black disabled:opacity-50"
              >
                Assign Plan
              </button>
            </div>
          </div>
        )}

        {/* Patient Data Display */}
        {patientData && (
          <>
            {/* Patient Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20 border border-neon-cyan/30 rounded-xl p-6">
                <p className="text-gray-400 text-sm mb-1">Patient</p>
                <p className="text-2xl font-bold text-white">{patientData.profile.username}</p>
              </div>

              <div className="bg-gradient-to-br from-green-500/20 to-emerald-500/20 border border-green-500/30 rounded-xl p-6">
                <p className="text-gray-400 text-sm">Total Sessions</p>
                <p className="text-3xl font-bold text-green-400">{patientData.profile.total_sessions}</p>
              </div>

              <div className="bg-gradient-to-br from-neon-cyan/20 to-blue-500/20 border border-neon-cyan/30 rounded-xl p-6">
                <p className="text-gray-400 text-sm">Avg Form Quality</p>
                <p className="text-3xl font-bold text-neon-cyan">{patientData.avg_form_quality.toFixed(0)}%</p>
              </div>

              <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 border border-orange-500/30 rounded-xl p-6">
                <p className="text-gray-400 text-sm">Current Streak</p>
                <p className="text-3xl font-bold text-orange-400">{patientData.profile.current_streak} days</p>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <ClipboardPlus size={20} className="text-neon-cyan" /> Plan Adherence
              </h3>
              {patientData.assignments.length === 0 ? (
                <p className="text-gray-400">No plan has been assigned yet.</p>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {patientData.assignments.map(assignment => (
                    <div key={assignment.assignment_id} className="rounded-lg border border-white/10 bg-gray-800 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-bold text-white">{assignment.plan.name}</p>
                          <p className="text-xs text-gray-400">{assignment.plan.durationWeeks}-week plan</p>
                        </div>
                        <span className="rounded-full bg-neon-cyan/10 px-2 py-1 text-xs capitalize text-neon-cyan">
                          {assignment.status}
                        </span>
                      </div>
                      <p className="mt-3 text-sm text-gray-300">{assignment.completed_sessions} prescribed sessions completed</p>
                      <p className="mt-1 text-xs text-gray-500">
                        {assignment.last_completed_at
                          ? `Last completed ${new Date(assignment.last_completed_at).toLocaleDateString()}`
                          : 'No completed session yet'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* Form Quality Chart */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                  <TrendingUp size={20} className="text-neon-cyan" />
                  Daily Form Quality
                </h3>
                <p className="mb-4 text-xs text-gray-500">Average quality across sessions on each active day</p>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="date" stroke="#888" />
                    <YAxis stroke="#888" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #00d9ff' }}
                      labelStyle={{ color: '#fff' }}
                      labelFormatter={(_, payload) => {
                        const point = payload?.[0]?.payload;
                        return point ? `${point.fullDate} • ${point.sessionCount} session${point.sessionCount === 1 ? '' : 's'}` : '';
                      }}
                      formatter={(value) => [`${Number(value).toFixed(1)}%`, 'Average quality']}
                    />
                    <Line
                      type="monotone"
                      dataKey="averageQuality"
                      stroke="#00d9ff"
                      strokeWidth={2}
                      dot={{ fill: '#00d9ff' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Reps Chart */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                  <BarChart3 size={20} className="text-neon-cyan" />
                  Daily Repetitions
                </h3>
                <p className="mb-4 text-xs text-gray-500">Total repetitions across sessions on each active day</p>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="date" stroke="#888" />
                    <YAxis stroke="#888" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #00d9ff' }}
                      labelStyle={{ color: '#fff' }}
                      labelFormatter={(_, payload) => {
                        const point = payload?.[0]?.payload;
                        return point ? `${point.fullDate} • ${point.sessionCount} session${point.sessionCount === 1 ? '' : 's'}` : '';
                      }}
                      formatter={(value) => [Number(value), 'Total reps']}
                    />
                    <Bar dataKey="totalReps" fill="#00d9ff" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Session History */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <Zap size={20} className="text-neon-cyan" />
                Recent Sessions
              </h3>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {patientData.sessions.map((session, idx) => (
                  <div key={idx} className="flex items-center justify-between p-4 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors">
                    <div>
                      <p className="font-bold text-white">{session.exercise_name}</p>
                      <p className="text-sm text-gray-400">
                        {new Date(session.date).toLocaleString([], {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                        })} • {session.total_reps} reps
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-neon-cyan">{session.xp_earned} XP</p>
                      <p className="text-sm text-gray-400">{session.form_quality.toFixed(0)}% form</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Empty State */}
        {!patientData && !loading && (
          <div className="bg-gray-900 border border-dashed border-gray-700 rounded-xl p-12 text-center">
            <Search className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400 text-lg">Select a linked patient or search for a new patient</p>
          </div>
        )}
          </main>
        </div>
      </div>
    </div>
  );
}
