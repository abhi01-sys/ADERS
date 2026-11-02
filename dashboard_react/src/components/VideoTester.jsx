import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Upload, Camera, Play, Square, AlertTriangle, CheckCircle,
  Navigation, MapPin, RefreshCw, Crosshair, Radio, Zap,
  Sliders, Cpu, Video, CheckCircle2, ShieldAlert, Sparkles, Layers
} from 'lucide-react'
import {
  createIncident,
  detectVideoFile,
  uploadVideoStream,
  detectFrame,
  getVideoStreamUrl,
} from '../api/incidents'
import toast from 'react-hot-toast'

const LOCATION_PRESETS = {
  'Custom Coordinates':         { lat: 28.6139,  lon: 77.2090  },
  'College Campus Main Gate':   { lat: 12.9716,  lon: 77.5946  },
  'Highway NH-44 KM-12':        { lat: 28.4595,  lon: 77.0266  },
  'Downtown Intersection':      { lat: 19.0760,  lon: 72.8777  },
  'Airport Road Junction':      { lat: 12.9900,  lon: 77.6100  },
}

export function VideoTester({ onIncidentCreated }) {
  const [source, setSource]             = useState('upload') // 'upload' | 'webcam'
  const [videoURL, setVideoURL]         = useState(null)
  const [rawFile, setRawFile]           = useState(null)
  const [isAnalyzing, setIsAnalyzing]   = useState(false)
  const [isStreaming, setIsStreaming]   = useState(false)

  // Live detection streaming state
  const [isLiveAiActive, setIsLiveAiActive]             = useState(false)
  const [liveStreamUrl, setLiveStreamUrl]               = useState(null)
  const [webcamAnnotatedFrame, setWebcamAnnotatedFrame] = useState(null)
  const [webcamInferenceMs, setWebcamInferenceMs]       = useState(null)
  
  // Location options: 'live' (device/camera GPS) | 'custom' (presets or manual coordinates)
  const [locationMode, setLocationMode] = useState('live')
  const [isFetchingGps, setIsFetchingGps] = useState(false)
  const [gpsAccuracy, setGpsAccuracy]   = useState(null)
  const [preset, setPreset]             = useState('College Campus Main Gate')
  const [customLat, setCustomLat]       = useState(12.9716)
  const [customLon, setCustomLon]       = useState(77.5946)

  const [camLabel, setCamLabel]               = useState('CAM_LIVE_01')
  const [detections, setDetections]           = useState([])
  const [confThresh, setConfThresh]           = useState(0.50) // Optimal calibrated threshold to prevent pre-crash triggers
  const [performanceMode, setPerformanceMode] = useState('fast') // 'fast' (CPU 30fps) | 'quality'

  const videoRef      = useRef(null)
  const streamRef     = useRef(null)
  const fileRef       = useRef(null)
  const canvasRef     = useRef(null)
  const liveTimerRef  = useRef(null)

  const lat = customLat
  const lon = customLon

  // Fetch live GPS location from device / browser
  const fetchLiveLocation = useCallback(() => {
    if (!navigator.geolocation) {
      toast.error('Geolocation is not supported by your browser')
      setLocationMode('custom')
      return
    }

    setIsFetchingGps(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords
        const latVal = parseFloat(latitude.toFixed(6))
        const lonVal = parseFloat(longitude.toFixed(6))
        setCustomLat(latVal)
        setCustomLon(lonVal)
        setGpsAccuracy(Math.round(accuracy))
        setIsFetchingGps(false)
        toast.success(`📍 Live GPS Locked: ${latVal.toFixed(4)}, ${lonVal.toFixed(4)} (±${Math.round(accuracy)}m)`, {
          style: {
            borderRadius: '12px',
            background: '#0e1629',
            color: '#fff',
            border: '1px solid rgba(16, 185, 129, 0.3)',
          }
        })
      },
      (err) => {
        setIsFetchingGps(false)
        toast.error(`GPS Notice: ${err.message || 'Permission denied'}. Defaulting to presets.`)
        setLocationMode('custom')
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    )
  }, [])

  // Auto-acquire GPS on mount or when switching to live location
  useEffect(() => {
    if (locationMode === 'live') {
      fetchLiveLocation()
    }
  }, [locationMode, fetchLiveLocation])

  // Sync presets when in custom location mode
  useEffect(() => {
    if (locationMode === 'custom' && preset !== 'Custom Coordinates' && LOCATION_PRESETS[preset]) {
      setCustomLat(LOCATION_PRESETS[preset].lat)
      setCustomLon(LOCATION_PRESETS[preset].lon)
    }
  }, [preset, locationMode])

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setRawFile(file)
    const url = URL.createObjectURL(file)
    setVideoURL(url)
    toast.success(`Loaded video: ${file.name}`, { icon: '🎬' })
  }

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 360 } }
      })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
      setIsStreaming(true)
      setIsLiveAiActive(true)
      toast.success('Webcam connected! Real-time YOLO detection online.', { icon: '📹' })
    } catch {
      toast.error('Could not access webcam. Please check browser permissions.')
    }
  }

  const stopWebcam = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }

  const handleStart = () => {
    if (source === 'webcam') {
      startWebcam()
    } else {
      setIsStreaming(true)
    }
  }

  const handleStop = () => {
    stopWebcam()
    setIsStreaming(false)
    setIsLiveAiActive(false)
    setLiveStreamUrl(null)
    setWebcamAnnotatedFrame(null)
    setWebcamInferenceMs(null)
    if (liveTimerRef.current) {
      clearInterval(liveTimerRef.current)
      liveTimerRef.current = null
    }
  }

  // Live webcam frame processor loop (Zero-backlog async queue)
  useEffect(() => {
    if (source !== 'webcam' || !isStreaming || !isLiveAiActive) {
      if (liveTimerRef.current) {
        clearTimeout(liveTimerRef.current)
        liveTimerRef.current = null
      }
      return
    }

    let isMounted = true

    const captureAndSend = () => {
      if (!isMounted) return
      if (!videoRef.current || videoRef.current.readyState < 2) {
        liveTimerRef.current = setTimeout(captureAndSend, 60)
        return
      }

      const video = videoRef.current
      const canvas = canvasRef.current || document.createElement('canvas')
      canvas.width = 480
      canvas.height = 270
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      canvas.toBlob(async (blob) => {
        if (!blob || !isMounted) {
          if (isMounted) liveTimerRef.current = setTimeout(captureAndSend, 40)
          return
        }

        const fd = new FormData()
        fd.append('file', blob, 'frame.jpg')
        fd.append('camera_id', camLabel)
        fd.append('location_lat', lat)
        fd.append('location_lon', lon)
        fd.append('conf_threshold', confThresh)
        fd.append('confirmation_frames', 8)

        const startT = performance.now()
        try {
          const res = await detectFrame(fd)
          if (!isMounted) return
          setWebcamInferenceMs(Math.round(performance.now() - startT))
          if (res.image) {
            setWebcamAnnotatedFrame(res.image)
          }
          if (res.accident_detected && res.incident) {
            setDetections((prev) => [res.incident, ...prev.slice(0, 9)])
            onIncidentCreated?.()
          }
        } catch {
          // ignore transient frame network drops
        } finally {
          if (isMounted) {
            liveTimerRef.current = setTimeout(captureAndSend, 25)
          }
        }
      }, 'image/jpeg', 0.70)
    }

    liveTimerRef.current = setTimeout(captureAndSend, 80)

    return () => {
      isMounted = false
      if (liveTimerRef.current) {
        clearTimeout(liveTimerRef.current)
        liveTimerRef.current = null
      }
    }
  }, [source, isStreaming, isLiveAiActive, camLabel, lat, lon, confThresh, onIncidentCreated])

  // Uploaded video: start real-time YOLOv8 MJPEG detection stream
  const handleStartLiveVideoStream = async () => {
    if (!rawFile) {
      toast.error('Please upload a video file first!')
      return
    }
    setIsAnalyzing(true)
    const toastId = toast.loading('Initializing live YOLOv8 detection stream...')

    try {
      const formData = new FormData()
      formData.append('file', rawFile)

      const uploadRes = await uploadVideoStream(formData)
      toast.dismiss(toastId)
      toast.success('Live YOLOv8 Detection Stream Online!', {
        icon: '⚡',
        style: {
          borderRadius: '12px',
          background: '#0e1629',
          color: '#fff',
          border: '1px solid rgba(59, 130, 246, 0.4)',
        }
      })

      const streamUrl = getVideoStreamUrl(uploadRes.video_id, {
        cameraId: camLabel,
        lat,
        lon,
        conf: confThresh,
        confirmationFrames: 10,
        skipFrames: performanceMode === 'fast' ? 2 : 1,
      })

      setLiveStreamUrl(streamUrl)
      setIsLiveAiActive(true)
      setIsStreaming(true)
    } catch {
      toast.dismiss(toastId)
      toast.error('Failed to start stream — please ensure the FastAPI backend is running.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleRunAIAnalysis = async () => {
    if (!rawFile) {
      toast.error('Please upload a video file first!')
      return
    }
    setIsAnalyzing(true)
    const toastId = toast.loading('Executing fine-tuned YOLOv8 model scan on video...')

    try {
      const formData = new FormData()
      formData.append('file', rawFile)
      formData.append('camera_id', camLabel)
      formData.append('location_lat', lat)
      formData.append('location_lon', lon)
      formData.append('conf_threshold', confThresh)
      formData.append('confirmation_frames', 10)

      const result = await detectVideoFile(formData)
      toast.dismiss(toastId)

      if (result.accidents_detected > 0) {
        toast.success(`Scan Complete: ${result.accidents_detected} accident(s) detected and registered!`, { duration: 6000 })
        setDetections((prev) => [...result.incidents, ...prev])
      } else {
        toast.success(`Processed ${result.processed_frames} frames: Normal traffic flow, no accidents.`, { duration: 5000 })
      }
      onIncidentCreated?.()
    } catch (err) {
      toast.dismiss(toastId)
      toast.error('Analysis failed — check backend terminal output.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  // Simulation button for college demonstration
  const simulateDetection = async (severity = 'major') => {
    const entry = {
      id: Date.now(),
      camera_id: camLabel,
      confidence: 0.84 + Math.random() * 0.12,
      severity,
      location_lat: lat,
      location_lon: lon,
      snapshot_path: null,
    }
    setDetections((prev) => [entry, ...prev.slice(0, 9)])

    try {
      const created = await createIncident({
        camera_id: camLabel,
        confidence: parseFloat(entry.confidence.toFixed(2)),
        severity,
        location_lat: lat,
        location_lon: lon,
      })
      toast.success(`${severity.toUpperCase()} accident logged into database (ID #${created.id})`, {
        icon: '🚨'
      })
      onIncidentCreated?.()
    } catch {
      toast.error('Could not register incident — is the backend running?')
    }
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 animate-fade-in">
      
      {/* ── Left Settings & Control Console ─────────────────────────────────── */}
      <div className="card space-y-5 border border-white/10 shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/10 pb-3.5">
          <h3 className="font-bold text-sm text-white flex items-center gap-2">
            <Sliders size={16} className="text-blue-400" />
            Surveillance & AI Studio Controls
          </h3>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
            ENGINE READY
          </span>
        </div>

        {/* Source Switcher */}
        <div>
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5 font-mono">
            Input Video Feed
          </label>
          <div className="grid grid-cols-2 gap-2 bg-dark-950/80 p-1 rounded-xl border border-white/10">
            {[
              { id: 'upload', label: 'Video File', icon: Video },
              { id: 'webcam', label: 'Live Camera', icon: Camera },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => { setSource(id); handleStop() }}
                className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all ${
                  source === id
                    ? 'bg-blue-600 text-white shadow-glow-sm shadow-blue-900/50'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* File Upload Zone */}
        {source === 'upload' && (
          <div>
            <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5 font-mono">
              Test Video Clip (.mp4, .avi, .mov)
            </label>
            <div
              onClick={() => fileRef.current?.click()}
              className="group border border-dashed border-white/15 hover:border-blue-500/50 hover:bg-blue-500/5 rounded-2xl p-5 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all text-center"
            >
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center group-hover:scale-110 transition-transform">
                <Upload size={18} />
              </div>
              <p className="text-xs font-semibold text-slate-200 group-hover:text-blue-300">
                {rawFile ? rawFile.name : 'Click to select CCTV/traffic video'}
              </p>
              <p className="text-[11px] text-slate-500">
                {rawFile ? `${(rawFile.size / 1024 / 1024).toFixed(1)} MB loaded` : 'Supports dashcam or CCTV footage up to 50MB'}
              </p>
            </div>
            <input ref={fileRef} type="file" accept="video/*" className="hidden" onChange={handleFileChange} />
          </div>
        )}

        {/* Location Selector */}
        <div className="space-y-2.5">
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block font-mono">
            Geospatial Location Tagging
          </label>
          
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setLocationMode('live')}
              className={`py-2 px-3 rounded-xl text-xs font-semibold border flex items-center justify-center gap-1.5 transition-all ${
                locationMode === 'live'
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 border-blue-500 text-white shadow-glow-sm'
                  : 'bg-dark-950/80 border-white/10 text-slate-400 hover:text-slate-200'
              }`}
            >
              <Navigation size={13} className={isFetchingGps ? 'animate-spin' : ''} />
              Live Device GPS
            </button>
            <button
              type="button"
              onClick={() => setLocationMode('custom')}
              className={`py-2 px-3 rounded-xl text-xs font-semibold border flex items-center justify-center gap-1.5 transition-all ${
                locationMode === 'custom'
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 border-blue-500 text-white shadow-glow-sm'
                  : 'bg-dark-950/80 border-white/10 text-slate-400 hover:text-slate-200'
              }`}
            >
              <MapPin size={13} />
              Predefined Presets
            </button>
          </div>

          {/* Mode: Live GPS */}
          {locationMode === 'live' && (
            <div className="p-3 bg-dark-950/80 border border-white/10 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-300 flex items-center gap-2 font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Device GPS Telemetry Active
                </span>
                <button
                  type="button"
                  onClick={fetchLiveLocation}
                  disabled={isFetchingGps}
                  className="text-blue-400 hover:text-blue-300 flex items-center gap-1 text-[11px] font-medium disabled:opacity-50"
                >
                  <RefreshCw size={11} className={isFetchingGps ? 'animate-spin' : ''} />
                  {isFetchingGps ? 'Syncing...' : 'Re-sync'}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="bg-dark-900 p-2 rounded-lg border border-white/5">
                  <span className="text-[10px] text-slate-500 block font-sans font-semibold">LATITUDE</span>
                  <span className="text-slate-200 font-bold">{customLat.toFixed(6)}</span>
                </div>
                <div className="bg-dark-900 p-2 rounded-lg border border-white/5">
                  <span className="text-[10px] text-slate-500 block font-sans font-semibold">LONGITUDE</span>
                  <span className="text-slate-200 font-bold">{customLon.toFixed(6)}</span>
                </div>
              </div>

              {gpsAccuracy !== null && (
                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-0.5">
                  <span>Signal Precision:</span>
                  <span className="text-emerald-400 font-mono font-medium">±{gpsAccuracy}m radius</span>
                </div>
              )}
            </div>
          )}

          {/* Mode: Presets */}
          {locationMode === 'custom' && (
            <div className="p-3 bg-dark-950/80 border border-white/10 rounded-xl space-y-2.5">
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Preset Sector</label>
                <select
                  value={preset}
                  onChange={(e) => setPreset(e.target.value)}
                  className="w-full bg-dark-900 border border-white/10 text-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-blue-500/50"
                >
                  {Object.keys(LOCATION_PRESETS).map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-500 block font-semibold">LATITUDE</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customLat}
                    onChange={(e) => {
                      setPreset('Custom Coordinates')
                      setCustomLat(parseFloat(e.target.value) || 0)
                    }}
                    className="w-full bg-dark-900 border border-white/10 text-slate-200 rounded-lg px-2.5 py-1 text-xs font-mono mt-1 focus:outline-none focus:border-blue-500/50"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 block font-semibold">LONGITUDE</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customLon}
                    onChange={(e) => {
                      setPreset('Custom Coordinates')
                      setCustomLon(parseFloat(e.target.value) || 0)
                    }}
                    className="w-full bg-dark-900 border border-white/10 text-slate-200 rounded-lg px-2.5 py-1 text-xs font-mono mt-1 focus:outline-none focus:border-blue-500/50"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Camera sector identifier */}
        <div>
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1 font-mono">
            Camera Sector Tag
          </label>
          <input
            value={camLabel}
            onChange={(e) => setCamLabel(e.target.value)}
            className="w-full bg-dark-950/80 border border-white/10 text-slate-200 rounded-xl px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-blue-500/50"
          />
        </div>

        {/* Sensitivity Calibration Slider */}
        <div className="p-3 bg-dark-950/80 border border-white/10 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono">
              AI Confidence Threshold
            </span>
            <span className="text-xs font-mono font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-lg border border-blue-500/20">
              {confThresh.toFixed(2)}
            </span>
          </div>

          <input
            type="range"
            min="0.15"
            max="0.80"
            step="0.02"
            value={confThresh}
            onChange={(e) => setConfThresh(+e.target.value)}
            className="w-full accent-blue-500 cursor-pointer"
          />

          <p className="text-[11px] leading-tight">
            {confThresh < 0.40 ? (
              <span className="text-amber-400 font-medium">⚠️ High Sensitivity (May trigger early during close approach)</span>
            ) : confThresh <= 0.60 ? (
              <span className="text-emerald-400 font-medium">🟢 Optimal Post-Impact (Calibrated to trigger on confirmed crash)</span>
            ) : (
              <span className="text-red-400 font-medium">🔴 Strict (Only triggers on high-confidence severe wreckage)</span>
            )}
          </p>
        </div>

        {/* Performance Mode Switcher */}
        <div>
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5 font-mono">
            Inference Performance Profile
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setPerformanceMode('fast')}
              className={`py-1.5 px-2.5 rounded-xl text-xs font-semibold border flex items-center justify-center gap-1.5 transition-all ${
                performanceMode === 'fast'
                  ? 'bg-emerald-600/30 text-emerald-300 border-emerald-500/50 shadow-glow-emerald'
                  : 'bg-dark-950/80 border-white/10 text-slate-400 hover:text-slate-200'
              }`}
            >
              🚀 Fast (30 FPS CPU)
            </button>
            <button
              type="button"
              onClick={() => setPerformanceMode('quality')}
              className={`py-1.5 px-2.5 rounded-xl text-xs font-semibold border flex items-center justify-center gap-1.5 transition-all ${
                performanceMode === 'quality'
                  ? 'bg-blue-600/30 text-blue-300 border-blue-500/50 shadow-glow-blue'
                  : 'bg-dark-950/80 border-white/10 text-slate-400 hover:text-slate-200'
              }`}
            >
              🎯 Full Every Frame
            </button>
          </div>
        </div>

        {/* Action Execution Triggers */}
        {source === 'upload' && rawFile && (
          <div className="space-y-2 pt-1">
            <button
              onClick={handleStartLiveVideoStream}
              disabled={isAnalyzing || (isLiveAiActive && Boolean(liveStreamUrl))}
              className="btn-primary w-full flex items-center justify-center gap-2 py-3"
            >
              {isAnalyzing ? (
                <>⏳ Initializing Video Pipeline...</>
              ) : isLiveAiActive && liveStreamUrl ? (
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                  Streaming Live YOLOv8 Detection
                </span>
              ) : (
                <>
                  <Zap size={16} />
                  Stream Live YOLOv8 Detections
                </>
              )}
            </button>

            <button
              onClick={handleRunAIAnalysis}
              disabled={isAnalyzing || isLiveAiActive}
              className="btn-secondary w-full flex items-center justify-center gap-2 text-xs py-2 disabled:opacity-40"
            >
              <Layers size={14} />
              Quick Batch File Scan
            </button>
          </div>
        )}

        {/* Webcam Action Button */}
        {source === 'webcam' && (
          <div className="space-y-2 pt-1">
            <button
              onClick={isStreaming ? handleStop : handleStart}
              className={`w-full py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all ${
                isStreaming
                  ? 'bg-red-600 hover:bg-red-500 text-white shadow-glow-red'
                  : 'btn-glow-blue'
              }`}
            >
              {isStreaming ? (
                <>
                  <Square size={16} />
                  Stop Live Webcam AI
                </>
              ) : (
                <>
                  <Zap size={16} />
                  Start Live AI Webcam Stream
                </>
              )}
            </button>
            {isStreaming && webcamInferenceMs && (
              <p className="text-[11px] text-emerald-400 text-center font-mono">
                ⚡ Inference Latency: {webcamInferenceMs}ms
              </p>
            )}
          </div>
        )}

        {/* Normal play/stop for uploaded clip */}
        {source === 'upload' && videoURL && !isLiveAiActive && (
          <div className="flex gap-2">
            <button
              onClick={handleStart}
              disabled={isStreaming}
              className="btn-secondary flex-1 flex items-center justify-center gap-1.5 text-xs py-2"
            >
              <Play size={14} /> Local Play
            </button>
            <button
              onClick={handleStop}
              disabled={!isStreaming}
              className="btn-secondary flex-1 flex items-center justify-center gap-1.5 text-xs py-2"
            >
              <Square size={14} /> Pause
            </button>
          </div>
        )}

        {/* College Demo Diagnostic Triggers */}
        <div className="border-t border-white/10 pt-3">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 font-mono">
            College Evaluation Simulation Triggers
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => simulateDetection('major')}
              className="py-1.5 px-2 rounded-lg text-xs font-bold bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 transition-colors"
            >
              Simulate MAJOR Crash
            </button>
            <button
              onClick={() => simulateDetection('minor')}
              className="py-1.5 px-2 rounded-lg text-xs font-bold bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 transition-colors"
            >
              Simulate MODERATE
            </button>
          </div>
        </div>

      </div>

      {/* ── Right Tactical CCTV Surveillance Viewport ────────────────────── */}
      <div className="xl:col-span-2 card p-0 overflow-hidden flex flex-col border border-white/10 shadow-2xl">
        {/* Top Camera Status Bar */}
        <div className="px-5 py-3.5 bg-dark-900/90 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />
            <span className="font-mono text-xs font-bold text-slate-200 tracking-wider">
              FEED // {camLabel}
            </span>
            <span className="text-slate-600">•</span>
            <span className="text-[11px] font-mono text-slate-400">1080p AI-Overlay</span>
          </div>

          <div className="flex items-center gap-3">
            {isStreaming && (
              <span className="flex items-center gap-1.5 text-red-400 text-xs font-mono font-bold bg-red-500/10 px-2.5 py-0.5 rounded-full border border-red-500/30">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                ● REC [LIVE]
              </span>
            )}
            <span className="text-[11px] font-mono text-slate-500">
              {performanceMode === 'fast' ? '30 FPS OPTIMIZED' : 'EVERY FRAME SCAN'}
            </span>
          </div>
        </div>

        {/* Viewport Screen */}
        <div className="relative bg-black flex-1 min-h-[380px] max-h-[460px] flex items-center justify-center overflow-hidden">
          {/* Tactical HUD Crosshair Overlays */}
          <div className="hud-corner-tl z-20 pointer-events-none" />
          <div className="hud-corner-tr z-20 pointer-events-none" />
          <div className="hud-corner-bl z-20 pointer-events-none" />
          <div className="hud-corner-br z-20 pointer-events-none" />

          {/* Active View: Live MJPEG Stream */}
          {source === 'upload' && isLiveAiActive && liveStreamUrl ? (
            <div className="relative w-full h-full flex items-center justify-center">
              <img
                src={liveStreamUrl}
                alt="Live YOLOv8 Detection Stream"
                className="w-full h-full object-contain"
                onError={() => {
                  toast.error('Video stream ended or connection closed.')
                  handleStop()
                }}
              />
              <div className="absolute top-3 left-3 bg-dark-900/90 text-white text-[11px] font-bold px-3 py-1 rounded-xl flex items-center gap-2 border border-red-500/50 shadow-glow-red backdrop-blur-md z-30">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                <span>YOLOv8 ACCIDENT DETECTION ACTIVE</span>
              </div>
            </div>
          ) : source === 'webcam' && isLiveAiActive && webcamAnnotatedFrame ? (
            <div className="relative w-full h-full flex items-center justify-center">
              <img
                src={webcamAnnotatedFrame}
                alt="Live Webcam AI Detection"
                className="w-full h-full object-contain"
              />
              <video ref={videoRef} autoPlay muted playsInline className="hidden" />
              <div className="absolute top-3 left-3 bg-dark-900/90 text-white text-[11px] font-bold px-3 py-1 rounded-xl flex items-center gap-2 border border-blue-500/50 shadow-glow-blue backdrop-blur-md z-30">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                <span>LIVE WEBCAM YOLOv8 ACTIVE</span>
              </div>
              {webcamInferenceMs && (
                <div className="absolute top-3 right-3 bg-dark-900/90 text-emerald-400 font-mono text-[11px] px-2.5 py-1 rounded-lg border border-emerald-500/30 backdrop-blur-md z-30">
                  ⚡ {webcamInferenceMs}ms
                </div>
              )}
            </div>
          ) : source === 'upload' && videoURL ? (
            <video
              ref={videoRef}
              src={videoURL}
              controls
              autoPlay={isStreaming}
              className="w-full h-full object-contain"
            />
          ) : source === 'webcam' ? (
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-slate-600 py-24 gap-3">
              <div className="w-16 h-16 rounded-2xl bg-dark-900 border border-white/5 flex items-center justify-center text-slate-500">
                <Camera size={28} />
              </div>
              <p className="text-sm font-semibold text-slate-400">
                No Active Camera Feed Selected
              </p>
              <p className="text-xs text-slate-600 max-w-xs text-center">
                Select a test traffic video clip on the left or click 'Start Live AI Webcam' to activate real-time inference.
              </p>
            </div>
          )}

          {/* Off-screen canvas for frame extraction */}
          <canvas ref={canvasRef} className="hidden" />
        </div>

        {/* ── Recent Detections Timeline Under Viewport ────────────────────── */}
        <div className="border-t border-white/10 bg-dark-950/60 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">
              Real-Time Incident Stream
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              {detections.length} Events Logged
            </span>
          </div>

          {detections.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-1">
              Normal traffic conditions. AI accident confirmation triggers will appear here in real-time.
            </p>
          ) : (
            <div className="flex gap-2.5 overflow-x-auto pb-1">
              {detections.map((d, idx) => (
                <div
                  key={d.id || idx}
                  className={`min-w-[190px] p-2.5 rounded-xl border ${
                    d.severity === 'major'
                      ? 'bg-red-950/40 border-red-500/30 text-red-200'
                      : 'bg-amber-950/40 border-amber-500/30 text-amber-200'
                  } flex flex-col gap-1 text-xs animate-slide-up shadow-lg`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-extrabold text-[10px] uppercase tracking-wider">
                      {d.severity} ACCIDENT
                    </span>
                    <span className="font-mono text-[10px] font-bold">
                      {((d.confidence || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-300 font-mono">
                    {d.camera_id}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {typeof d.location_lat === 'number'
                      ? `${d.location_lat.toFixed(4)}, ${d.location_lon.toFixed(4)}`
                      : 'GPS Tagged'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

    </div>
  )
}
