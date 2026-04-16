import axios from 'axios'

// In production (Vercel), VITE_API_URL points to Railway backend
// In development, empty string uses Vite proxy
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const API_BASE = import.meta.env.VITE_API_URL || ''

export function imageUrl(path) {
  if (!path) return ''
  if (path.startsWith('data:')) return path
  if (path.startsWith('http')) return path
  return API_BASE + path
}

export default api
