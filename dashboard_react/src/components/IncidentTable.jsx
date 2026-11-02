import { useState, useMemo } from 'react'
import { format } from 'date-fns'
import {
  MapPin, CheckCircle2, Clock, AlertTriangle, ExternalLink,
  Search, Filter, ShieldCheck, UserCheck, Image as ImageIcon
} from 'lucide-react'
import { ackIncident } from '../api/incidents'
import toast from 'react-hot-toast'

function SeverityBadge({ severity }) {
  if (severity === 'major') {
    return (
      <span className="badge-major">
        <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
        MAJOR
      </span>
    )
  }
  return (
    <span className="badge-minor">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
      MODERATE
    </span>
  )
}

function StatusBadge({ acknowledged, alertSent }) {
  if (acknowledged) {
    return (
      <span className="badge-acked">
        <CheckCircle2 size={12} className="text-emerald-400" />
        RESOLVED
      </span>
    )
  }
  if (alertSent) {
    return (
      <span className="badge-sent">
        <Clock size={12} className="text-blue-400 animate-spin" />
        ALERT DISPATCHED
      </span>
    )
  }
  return (
    <span className="badge-pending">
      <Clock size={12} />
      DETECTED
    </span>
  )
}

export function IncidentTable({ incidents, onAck }) {
  const [ackingId, setAckingId] = useState(null)
  const [responder, setResponder] = useState('Campus Emergency Unit')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterSeverity, setFilterSeverity] = useState('all') // 'all' | 'major' | 'minor' | 'unacked'

  const handleAck = async (id) => {
    setAckingId(id)
    try {
      await ackIncident(id, responder)
      toast.success(`Incident #${id} acknowledged by ${responder}`, {
        icon: '🛡️',
        style: {
          borderRadius: '12px',
          background: '#0e1629',
          color: '#fff',
          border: '1px solid rgba(16, 185, 129, 0.3)',
        }
      })
      onAck?.()
    } catch {
      toast.error('Failed to acknowledge — backend offline?')
    } finally {
      setAckingId(null)
    }
  }

  // Filtered incidents
  const filtered = useMemo(() => {
    return incidents.filter((inc) => {
      // Search
      const matchesSearch =
        searchQuery === '' ||
        String(inc.id).includes(searchQuery) ||
        (inc.camera_id && inc.camera_id.toLowerCase().includes(searchQuery.toLowerCase()))

      if (!matchesSearch) return false

      // Severity / Status filter
      if (filterSeverity === 'major') return inc.severity === 'major'
      if (filterSeverity === 'minor') return inc.severity === 'minor'
      if (filterSeverity === 'unacked') return !inc.acknowledged

      return true
    })
  }, [incidents, searchQuery, filterSeverity])

  if (!incidents.length) {
    return (
      <div className="card text-center py-24 border-dashed border-white/10">
        <div className="w-16 h-16 rounded-2xl bg-slate-800/60 border border-white/10 flex items-center justify-center mx-auto mb-4 text-slate-500">
          <AlertTriangle size={32} />
        </div>
        <p className="font-bold text-slate-200 text-base">No Collision Incidents Recorded</p>
        <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
          The AI detection pipeline is actively scanning feeds. Once an accident occurs, it will automatically register here with GPS coordinates and Twilio call records.
        </p>
      </div>
    )
  }

  return (
    <div className="card p-0 overflow-hidden border border-white/10 shadow-2xl">
      {/* ── Top Toolbar ──────────────────────────────────────────────────────── */}
      <div className="p-4 bg-dark-900/90 border-b border-white/10 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by Cam ID or #..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-dark-950/80 border border-white/10 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
          />
        </div>

        {/* Filter chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {[
            { id: 'all', label: `All (${incidents.length})` },
            { id: 'major', label: `Major (${incidents.filter((i) => i.severity === 'major').length})` },
            { id: 'minor', label: `Moderate (${incidents.filter((i) => i.severity === 'minor').length})` },
            { id: 'unacked', label: `Action Needed (${incidents.filter((i) => !i.acknowledged).length})` },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setFilterSeverity(f.id)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                filterSeverity === f.id
                  ? 'bg-blue-600/30 text-blue-300 border border-blue-500/50'
                  : 'bg-dark-950/60 text-slate-400 hover:text-slate-200 border border-transparent'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Responder Badge */}
        <div className="flex items-center gap-2 border-l border-white/10 pl-3">
          <UserCheck size={14} className="text-blue-400" />
          <span className="text-[11px] text-slate-400">Responder:</span>
          <input
            value={responder}
            onChange={(e) => setResponder(e.target.value)}
            className="bg-dark-950/80 border border-white/10 text-xs text-slate-200 rounded-lg px-2.5 py-1 focus:outline-none focus:border-blue-500/50 max-w-[150px]"
          />
        </div>
      </div>

      {/* ── Table Viewport ─────────────────────────────────────────────────── */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/10 bg-dark-950/60 text-slate-400 uppercase tracking-wider font-mono text-[10px]">
              <th className="px-4 py-3 text-left">Incident</th>
              <th className="px-4 py-3 text-left">Timestamp</th>
              <th className="px-4 py-3 text-left">Feed / Camera</th>
              <th className="px-4 py-3 text-left">Severity</th>
              <th className="px-4 py-3 text-left">AI Confidence</th>
              <th className="px-4 py-3 text-left">GPS Coordinates</th>
              <th className="px-4 py-3 text-left">Dispatch Status</th>
              <th className="px-4 py-3 text-right">Emergency Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((inc) => {
              const lat = inc.location_lat
              const lon = inc.location_lon
              const hasCoords = lat !== null && lon !== null && lat !== undefined && lon !== undefined
              const mapsUrl = hasCoords ? `https://www.google.com/maps?q=${lat},${lon}` : null

              return (
                <tr
                  key={inc.id}
                  className="hover:bg-blue-600/5 transition-colors duration-150 animate-slide-up group"
                >
                  {/* ID */}
                  <td className="px-4 py-3.5 font-mono font-bold text-blue-400">
                    #{inc.id}
                  </td>

                  {/* Time */}
                  <td className="px-4 py-3.5 text-slate-300 font-mono whitespace-nowrap">
                    {inc.created_at ? format(new Date(inc.created_at), 'dd MMM, HH:mm:ss') : '—'}
                  </td>

                  {/* Camera */}
                  <td className="px-4 py-3.5 text-slate-200 font-medium flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                    <span className="font-mono text-[11px]">{inc.camera_id}</span>
                  </td>

                  {/* Severity */}
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <SeverityBadge severity={inc.severity} />
                  </td>

                  {/* Confidence Bar */}
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-dark-950 rounded-full h-1.5 overflow-hidden border border-white/10">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            inc.severity === 'major'
                              ? 'bg-gradient-to-r from-red-500 to-rose-400'
                              : 'bg-gradient-to-r from-amber-500 to-yellow-400'
                          }`}
                          style={{ width: `${Math.min(100, (inc.confidence || 0) * 100)}%` }}
                        />
                      </div>
                      <span className="font-mono font-semibold text-slate-300">
                        {((inc.confidence || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>

                  {/* GPS Coordinates */}
                  <td className="px-4 py-3.5">
                    {hasCoords ? (
                      <a
                        href={mapsUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 px-2 py-0.5 rounded-lg border border-blue-500/20 font-mono transition-colors"
                      >
                        <MapPin size={11} />
                        {Number(lat).toFixed(4)}, {Number(lon).toFixed(4)}
                        <ExternalLink size={9} className="opacity-70" />
                      </a>
                    ) : (
                      <span className="text-slate-600 font-mono">No GPS</span>
                    )}
                  </td>

                  {/* Dispatch Status */}
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <StatusBadge acknowledged={inc.acknowledged} alertSent={inc.alert_sent} />
                  </td>

                  {/* Action */}
                  <td className="px-4 py-3.5 text-right whitespace-nowrap">
                    {!inc.acknowledged ? (
                      <button
                        onClick={() => handleAck(inc.id)}
                        disabled={ackingId === inc.id}
                        className="btn-primary text-xs py-1.5 px-3 inline-flex items-center gap-1.5"
                      >
                        <ShieldCheck size={13} />
                        {ackingId === inc.id ? 'Confirming…' : 'Acknowledge'}
                      </button>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-emerald-400 font-medium px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                        <CheckCircle2 size={12} />
                        Verified
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
