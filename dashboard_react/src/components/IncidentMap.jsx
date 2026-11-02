import { useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { ExternalLink, MapPin, AlertTriangle, ShieldCheck, Crosshair, Layers } from 'lucide-react'

// Custom sleek radar pins for major vs minor
const makeIcon = (color, isMajor) =>
  L.divIcon({
    className: '',
    html: `<div style="
      position: relative;
      width: 32px; height: 32px;
      display: flex; align-items: center; justify-content: center;
    ">
      <div style="
        position: absolute; width: 100%; height: 100%;
        border-radius: 50%; background: ${color}; opacity: 0.35;
        animation: pulse 1.5s infinite;
      "></div>
      <div style="
        width: 18px; height: 18px; border-radius: 50%;
        background: ${color}; border: 3px solid #ffffff;
        box-shadow: 0 0 15px ${color};
      "></div>
    </div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  })

const iconMajor = makeIcon('#ef4444', true)
const iconMinor = makeIcon('#f59e0b', false)

// 100% Free & Open Tile Providers — NO API KEY OR WATERMARK REQUIRED
const MAP_PROVIDERS = {
  dark: {
    id: 'dark',
    label: 'Dark Tactical',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
    maxZoom: 16,
  },
  streets: {
    id: 'streets',
    label: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
  satellite: {
    id: 'satellite',
    label: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS',
    maxZoom: 18,
  },
}

function RecenterMap({ center }) {
  const map = useMap()
  if (center) map.setView(center, map.getZoom())
  return null
}

export function IncidentMap({ incidents }) {
  const [mapMode, setMapMode] = useState('dark')
  const withCoords = incidents.filter((i) => i.location_lat !== null && i.location_lon !== null)

  const center = withCoords.length
    ? [
        withCoords.reduce((s, i) => s + i.location_lat, 0) / withCoords.length,
        withCoords.reduce((s, i) => s + i.location_lon, 0) / withCoords.length,
      ]
    : [28.6139, 77.2090] // New Delhi default center fallback

  if (!withCoords.length) {
    return (
      <div className="card text-center py-24 border-dashed border-white/10">
        <Crosshair size={40} className="mx-auto mb-3 text-slate-500 animate-spin" />
        <p className="font-bold text-slate-200">No GPS Geospatial Coordinates Available</p>
        <p className="text-xs text-slate-500 mt-1">
          When an incident occurs in the Video Surveillance Studio, its latitude & longitude will pin here.
        </p>
      </div>
    )
  }

  const majorCount = withCoords.filter((i) => i.severity === 'major').length
  const currentProvider = MAP_PROVIDERS[mapMode] || MAP_PROVIDERS.dark

  return (
    <div className="space-y-4">
      {/* ── Tactical Header Bar ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
          <h3 className="font-bold text-sm text-slate-200">
            Real-Time Geospatial Incident Map
          </h3>
          <span className="text-xs font-mono text-slate-500">
            ({withCoords.length} Active Geo-Tags)
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Map Layer Switcher (No API Key Required) */}
          <div className="flex items-center bg-dark-900/90 border border-white/15 rounded-lg p-0.5 text-xs">
            {Object.values(MAP_PROVIDERS).map((prov) => (
              <button
                key={prov.id}
                onClick={() => setMapMode(prov.id)}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  mapMode === prov.id
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {prov.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="flex items-center gap-1.5 text-red-400 bg-red-950/60 border border-red-500/30 px-2.5 py-1 rounded-full font-semibold">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              {majorCount} Severe
            </span>
            <span className="flex items-center gap-1.5 text-amber-300 bg-amber-950/60 border border-amber-500/30 px-2.5 py-1 rounded-full font-semibold">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              {withCoords.length - majorCount} Moderate
            </span>
          </div>
        </div>
      </div>

      {/* ── Map Container ─────────────────────────────────────────────────── */}
      <div className="relative card p-0 overflow-hidden h-[460px] border border-white/15 shadow-2xl">
        {/* Tactical HUD corners */}
        <div className="hud-corner-tl" />
        <div className="hud-corner-tr" />
        <div className="hud-corner-bl" />
        <div className="hud-corner-br" />

        <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            key={currentProvider.id}
            url={currentProvider.url}
            attribution={currentProvider.attribution}
            maxZoom={currentProvider.maxZoom}
          />
          <RecenterMap center={center} />

          {withCoords.map((inc) => (
            <Marker
              key={inc.id}
              position={[inc.location_lat, inc.location_lon]}
              icon={inc.severity === 'major' ? iconMajor : iconMinor}
            >
              <Popup>
                <div className="p-1 space-y-2 text-slate-100 font-sans min-w-[200px]">
                  <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
                    <span className="font-bold text-xs text-blue-400">Incident #{inc.id}</span>
                    <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded-full ${
                      inc.severity === 'major' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-300'
                    }`}>
                      {inc.severity}
                    </span>
                  </div>

                  <div className="space-y-1 text-xs">
                    <p className="flex justify-between text-slate-300">
                      <span className="text-slate-500">Camera:</span>
                      <span className="font-mono">{inc.camera_id}</span>
                    </p>
                    <p className="flex justify-between text-slate-300">
                      <span className="text-slate-500">Confidence:</span>
                      <span className="font-mono text-emerald-400">{((inc.confidence || 0) * 100).toFixed(0)}%</span>
                    </p>
                    <p className="flex justify-between text-slate-300">
                      <span className="text-slate-500">Status:</span>
                      <span>{inc.acknowledged ? '✅ Dispatched' : '⏳ Action Needed'}</span>
                    </p>
                  </div>

                  <a
                    href={`https://www.google.com/maps?q=${inc.location_lat},${inc.location_lon}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 block text-center py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors"
                  >
                    Open in Google Maps Navigation
                  </a>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}
