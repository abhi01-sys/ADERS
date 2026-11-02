import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, AreaChart, Area } from 'recharts'
import { Activity, Clock, ShieldAlert } from 'lucide-react'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-dark-900/95 backdrop-blur-xl border border-white/20 px-3.5 py-2.5 rounded-xl text-xs text-slate-200 shadow-2xl">
      <p className="font-bold text-blue-400 font-mono">{label || payload[0].payload.name}</p>
      <p className="font-semibold mt-0.5">{payload[0].value} Incident(s) Recorded</p>
    </div>
  )
}

export function StatsChart({ incidents }) {
  // Group by camera_id
  const byCamera = incidents.reduce((acc, inc) => {
    acc[inc.camera_id] = (acc[inc.camera_id] || 0) + 1
    return acc
  }, {})

  const data = Object.entries(byCamera)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8)

  // Group by hour (last 12 hours)
  const now = Date.now()
  const hourly = Array.from({ length: 12 }, (_, i) => {
    const hourStart = now - (11 - i) * 3600000
    const hourEnd   = hourStart + 3600000
    const count = incidents.filter((inc) => {
      const t = new Date(inc.created_at).getTime()
      return t >= hourStart && t < hourEnd
    }).length
    const label = new Date(hourStart).getHours().toString().padStart(2, '0') + ':00'
    return { name: label, count }
  })

  if (!incidents.length) return null

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-fade-in">
      {/* Chart 1: By Camera Source */}
      <div className="card border border-white/10 shadow-2xl hover:border-blue-500/30 transition-all">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Activity size={16} />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
                Incidents by Camera Sector
              </h4>
              <p className="text-[11px] text-slate-500">Distribution across active monitoring nodes</p>
            </div>
          </div>
          <span className="text-xs font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">
            {data.length} Sectors Active
          </span>
        </div>

        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} barSize={26}>
            <defs>
              <linearGradient id="blueBar" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.4} />
              </linearGradient>
            </defs>
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} allowDecimals={false} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="count" fill="url(#blueBar)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Chart 2: Hourly Timeline */}
      <div className="card border border-white/10 shadow-2xl hover:border-rose-500/30 transition-all">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <Clock size={16} />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
                12-Hour Incident Velocity
              </h4>
              <p className="text-[11px] text-slate-500">Hourly detection frequency trend</p>
            </div>
          </div>
          <span className="text-xs font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
            Rolling Window
          </span>
        </div>

        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={hourly}>
            <defs>
              <linearGradient id="roseArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} allowDecimals={false} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="count" stroke="#ef4444" strokeWidth={2.5} fill="url(#roseArea)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
