import { useState, useCallback, useMemo } from 'react'
import toast from 'react-hot-toast'
import {
  AlertTriangle, Activity, Map, Video, Radio, RefreshCw, Wifi, WifiOff,
  ShieldAlert, Bell, Cpu, Zap, ExternalLink
} from 'lucide-react'
import { useIncidents }  from './hooks/useIncidents'
import { useWebSocket }  from './hooks/useWebSocket'
import { MetricCard }    from './components/MetricCard'
import { IncidentTable } from './components/IncidentTable'
import { IncidentMap }   from './components/IncidentMap'
import { VideoTester }   from './components/VideoTester'
import { StatsChart }    from './components/StatsChart'

const TABS = [
  { id: 'demo',      label: 'AI Surveillance Studio', icon: Video, badge: 'LIVE' },
  { id: 'incidents', label: 'Incident Log & Dispatch', icon: Activity },
  { id: 'map',       label: 'Tactical GPS Map',        icon: Map },
  { id: 'stats',     label: 'Emergency Analytics',     icon: Radio },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('demo')
  const { incidents, loading, error, refresh, addIncident } = useIncidents(6000)

  // WebSocket handler with rich glass toast
  const handleWsEvent = useCallback((msg) => {
    if (msg.event === 'new_incident') {
      addIncident(msg.payload)
      const sev = msg.payload.severity
      const isMajor = sev === 'major'

      toast.custom((t) => (
        <div
          className={`${
            t.visible ? 'animate-slide-up' : 'opacity-0'
          } max-w-md w-full bg-dark-900/95 backdrop-blur-2xl border ${
            isMajor ? 'border-red-500/50 shadow-glow-red' : 'border-amber-500/50 shadow-glow-amber'
          } rounded-2xl p-4 shadow-2xl flex items-start gap-3.5 text-slate-100 transition-all`}
        >
          <div className={`p-2.5 rounded-xl border ${
            isMajor ? 'bg-red-500/20 border-red-500/40 text-red-400' : 'bg-amber-500/20 border-amber-500/40 text-amber-300'
          } animate-pulse-fast`}>
            <AlertTriangle size={22} />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <span className={`text-[11px] font-black tracking-widest uppercase px-2 py-0.5 rounded-full ${
                isMajor ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              }`}>
                {sev.toUpperCase()} ACCIDENT
              </span>
              <span className="text-[11px] font-mono text-slate-400">
                Cam: {msg.payload.camera_id}
              </span>
            </div>

            <p className="font-bold text-sm text-white mt-1">
              Collision Confirmed: {((msg.payload.confidence || 0) * 100).toFixed(0)}% Confidence
            </p>
            <p className="text-xs text-slate-300 mt-0.5 flex items-center gap-1.5">
              <span>📞 Automated Twilio Voice Call & SMS Alert Dispatched</span>
            </p>
          </div>
        </div>
      ), { duration: 7000 })
    }
  }, [addIncident])

  useWebSocket(handleWsEvent)

  // Computed metrics
  const total   = incidents.length
  const major   = useMemo(() => incidents.filter((i) => i.severity === 'major').length, [incidents])
  const minor   = useMemo(() => incidents.filter((i) => i.severity === 'minor').length, [incidents])
  const unacked = useMemo(() => incidents.filter((i) => !i.acknowledged).length, [incidents])

  return (
    <div className="min-h-screen text-slate-100 font-sans selection:bg-blue-600/30 selection:text-blue-200">
      {/* ── Top Mission Control Header ───────────────────────────────────────── */}
      <header className="border-b border-white/10 bg-dark-950/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-screen-2xl mx-auto px-4 lg:px-8 py-3.5 flex items-center justify-between gap-4">
          
          {/* Brand & Emblem */}
          <div className="flex items-center gap-3.5">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-red-600 via-rose-600 to-amber-500 flex items-center justify-center text-xl shadow-glow-red border border-white/20">
                🚨
              </div>
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-dark-950 animate-ping" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-dark-950" />
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-lg tracking-tight text-white flex items-center gap-1.5">
                  ADERS
                  <span className="text-[10px] uppercase font-mono font-bold tracking-wider px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                    v0.1.0 AI
                  </span>
                </h1>
              </div>
              <p className="text-xs text-slate-400 font-medium">
                Autonomous Accident Detection & Emergency Response Command
              </p>
            </div>
          </div>

          {/* Navigation Pill Bar */}
          <nav className="hidden md:flex items-center gap-1.5 bg-dark-900/90 p-1.5 rounded-2xl border border-white/10 shadow-inner">
            {TABS.map(({ id, label, icon: Icon, badge }) => {
              const isActive = activeTab === id
              return (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`relative flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 ${
                    isActive
                      ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-glow-sm shadow-blue-900/50'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                  }`}
                >
                  <Icon size={14} className={isActive ? 'text-white' : 'text-slate-400'} />
                  <span>{label}</span>
                  {badge && (
                    <span className="text-[9px] font-black uppercase tracking-wider px-1.5 py-0.2 rounded-full bg-red-500 text-white animate-pulse">
                      {badge}
                    </span>
                  )}
                  {id === 'incidents' && unacked > 0 && (
                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-amber-500/30 text-amber-300 border border-amber-500/40">
                      {unacked}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>

          {/* Telemetry Status Indicators */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-dark-900/80 border border-white/10 text-xs">
              <Cpu size={13} className="text-blue-400" />
              <span className="font-mono text-slate-300 text-[11px]">YOLOv8 CPU</span>
              <span className="text-slate-600">•</span>
              {error ? (
                <span className="flex items-center gap-1.5 text-red-400 font-medium text-[11px]">
                  <WifiOff size={12} /> Offline
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-emerald-400 font-medium text-[11px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Sync
                </span>
              )}
            </div>

            <button
              onClick={refresh}
              title="Force Sync State"
              className="p-2.5 rounded-xl bg-dark-900/80 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors border border-white/10 active:scale-95"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin text-blue-400' : ''} />
            </button>
          </div>

        </div>

        {/* Mobile Navigation Row */}
        <div className="flex md:hidden px-4 pb-2.5 gap-1 overflow-x-auto">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap ${
                activeTab === id
                  ? 'bg-blue-600 text-white'
                  : 'bg-dark-900 text-slate-400'
              }`}
            >
              <Icon size={12} />
              {label}
            </button>
          ))}
        </div>
      </header>

      {/* ── Real-Time Mission Telemetry Cards ───────────────────────────────── */}
      <section className="max-w-screen-2xl mx-auto px-4 lg:px-8 pt-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Detections"
            value={loading ? '…' : total}
            color="blue"
            icon={Activity}
            sub="CCTV & Stream Logs"
          />
          <MetricCard
            label="Severe Collisions"
            value={loading ? '…' : major}
            color="red"
            icon={AlertTriangle}
            sub="High-Impact Crashes"
            trend={major > 0 ? 'CRITICAL' : null}
          />
          <MetricCard
            label="Moderate Incidents"
            value={loading ? '…' : minor}
            color="yellow"
            icon={ShieldAlert}
            sub="Minor Contact / Spin-out"
          />
          <MetricCard
            label="Pending Action"
            value={loading ? '…' : unacked}
            color={unacked > 0 ? 'orange' : 'green'}
            icon={Radio}
            sub={unacked > 0 ? 'Awaiting Dispatch Ack' : 'All Incidents Resolved'}
          />
        </div>
      </section>

      {/* ── Tab Viewports ─────────────────────────────────────────────────── */}
      <main className="max-w-screen-2xl mx-auto px-4 lg:px-8 py-6 space-y-6">

        {activeTab === 'demo' && (
          <VideoTester onIncidentCreated={refresh} />
        )}

        {activeTab === 'incidents' && (
          <IncidentTable incidents={incidents} onAck={refresh} />
        )}

        {activeTab === 'map' && (
          <IncidentMap incidents={incidents} />
        )}

        {activeTab === 'stats' && (
          <div className="space-y-6">
            <StatsChart incidents={incidents} />
            {incidents.length === 0 && (
              <div className="card text-center text-slate-400 py-20 border-dashed">
                <Activity size={44} className="mx-auto mb-3 text-slate-600 animate-pulse" />
                <p className="font-semibold text-slate-200">No Analytics Data Generated Yet</p>
                <p className="text-xs text-slate-500 mt-1">
                  Run a live video simulation or webcam test in the Surveillance Studio to see charts.
                </p>
              </div>
            )}
          </div>
        )}

      </main>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-6 text-center text-xs text-slate-500 bg-dark-950/40">
        <div className="flex items-center justify-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span>ADERS Core Engine v0.1.0 · YOLOv8 Computer Vision · FastREST API · Automated Twilio Dispatch</span>
        </div>
        <p className="text-[11px] text-slate-600 mt-1">
          Designed for Autonomous Emergency Response & Traffic Safety Surveillance
        </p>
      </footer>
    </div>
  )
}
