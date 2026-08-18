export interface SessionActivity {
  date: string;
  form_quality: number;
  total_reps: number;
}

export interface DailyActivity {
  dateKey: string;
  date: string;
  fullDate: string;
  timestamp: number;
  averageQuality: number;
  totalReps: number;
  sessionCount: number;
}

/** Group sessions by the user's local calendar day and return recent active days. */
export function buildDailyActivity(
  sessions: SessionActivity[],
  activeDayLimit: number = 7,
): DailyActivity[] {
  const groups = new Map<string, {
    timestamp: number;
    fullDate: string;
    qualityTotal: number;
    totalReps: number;
    sessionCount: number;
  }>();

  sessions.forEach(session => {
    const parsed = new Date(session.date);
    if (Number.isNaN(parsed.getTime())) return;

    const year = parsed.getFullYear();
    const month = parsed.getMonth();
    const day = parsed.getDate();
    const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const existing = groups.get(dateKey) || {
      timestamp: new Date(year, month, day).getTime(),
      fullDate: parsed.toLocaleDateString('en-US', {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      }),
      qualityTotal: 0,
      totalReps: 0,
      sessionCount: 0,
    };

    existing.qualityTotal += Number.isFinite(session.form_quality) ? session.form_quality : 0;
    existing.totalReps += Number.isFinite(session.total_reps) ? session.total_reps : 0;
    existing.sessionCount += 1;
    groups.set(dateKey, existing);
  });

  return Array.from(groups.entries())
    .map(([dateKey, group]) => ({
      dateKey,
      date: new Date(group.timestamp).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }),
      fullDate: group.fullDate,
      timestamp: group.timestamp,
      averageQuality: Number((group.qualityTotal / group.sessionCount).toFixed(1)),
      totalReps: group.totalReps,
      sessionCount: group.sessionCount,
    }))
    .sort((a, b) => a.timestamp - b.timestamp)
    .slice(-Math.max(1, activeDayLimit));
}
