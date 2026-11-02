import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 5000,
  headers: { 'Content-Type': 'application/json' },
})

export const getIncidents = (limit = 100) =>
  api.get(`/incidents/?limit=${limit}`).then((r) => r.data)

export const createIncident = (data) =>
  api.post('/incidents/', data).then((r) => r.data)

export const ackIncident = (id, responder, message = 'Acknowledged via Dashboard') =>
  api.post(`/incidents/${id}/ack`, { responder, message }).then((r) => r.data)

export const getIncidentAlerts = (id) =>
  api.get(`/incidents/${id}/alerts`).then((r) => r.data)

export const detectVideoFile = (formData) =>
  api.post('/incidents/detect-video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 minutes for full video inference
  }).then((r) => r.data)

export const uploadVideoStream = (formData) =>
  api.post('/incidents/upload-video-stream', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  }).then((r) => r.data)

export const detectFrame = (formData) =>
  api.post('/incidents/detect-frame', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 5000,
  }).then((r) => r.data)

export const getVideoStreamUrl = (videoId, { cameraId, lat, lon, conf, confirmationFrames = 10, skipFrames = 2 }) =>
  `/api/incidents/stream-video/${videoId}?camera_id=${encodeURIComponent(cameraId)}&location_lat=${lat}&location_lon=${lon}&conf_threshold=${conf}&confirmation_frames=${confirmationFrames}&skip_frames=${skipFrames}`

export const ping = () =>
  api.get('/ping').then((r) => r.data)

