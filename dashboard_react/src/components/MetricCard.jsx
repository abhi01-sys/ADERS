import React from 'react'

export function MetricCard({ label, value, icon: Icon, color = 'blue', sub, trend }) {
  const themes = {
    red: {
      border: 'border-red-500/30 hover:border-red-500/60',
      glow: 'shadow-[0_0_25px_-5px_rgba(239,68,68,0.2)]',
      iconBg: 'bg-red-500/10 border-red-500/30 text-red-400',
      accent: 'bg-red-500',
      text: 'text-red-400',
    },
    yellow: {
      border: 'border-amber-500/30 hover:border-amber-500/60',
      glow: 'shadow-[0_0_25px_-5px_rgba(245,158,11,0.2)]',
      iconBg: 'bg-amber-500/10 border-amber-500/30 text-amber-300',
      accent: 'bg-amber-500',
      text: 'text-amber-300',
    },
    orange: {
      border: 'border-orange-500/30 hover:border-orange-500/60',
      glow: 'shadow-[0_0_25px_-5px_rgba(249,115,22,0.2)]',
      iconBg: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
      accent: 'bg-orange-500',
      text: 'text-orange-400',
    },
    green: {
      border: 'border-emerald-500/30 hover:border-emerald-500/60',
      glow: 'shadow-[0_0_25px_-5px_rgba(16,185,129,0.2)]',
      iconBg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
      accent: 'bg-emerald-500',
      text: 'text-emerald-400',
    },
    blue: {
      border: 'border-blue-500/30 hover:border-blue-500/60',
      glow: 'shadow-[0_0_25px_-5px_rgba(59,130,246,0.2)]',
      iconBg: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
      accent: 'bg-blue-500',
      text: 'text-blue-400',
    },
  }

  const theme = themes[color] || themes.blue

  return (
    <div
      className={`relative overflow-hidden bg-dark-900/80 backdrop-blur-xl border ${theme.border} ${theme.glow} rounded-2xl p-5 transition-all duration-300 hover:-translate-y-1 group animate-fade-in`}
    >
      {/* Top subtle highlight line */}
      <div className={`absolute top-0 left-0 right-0 h-[2px] ${theme.accent} opacity-60 group-hover:opacity-100 transition-opacity`} />

      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold tracking-wider uppercase text-slate-400 font-mono">
            {label}
          </p>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-extrabold text-white tracking-tight font-sans">
              {value}
            </span>
            {trend && (
              <span className={`text-xs font-semibold ${theme.text}`}>
                {trend}
              </span>
            )}
          </div>
          {sub && (
            <p className="text-xs text-slate-400 mt-1 font-medium flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${theme.accent} animate-pulse`} />
              {sub}
            </p>
          )}
        </div>

        {Icon && (
          <div
            className={`p-3 rounded-xl border ${theme.iconBg} shadow-inner transition-transform group-hover:scale-110 duration-200`}
          >
            <Icon size={22} />
          </div>
        )}
      </div>

      {/* Decorative background glow circle */}
      <div
        className={`absolute -bottom-8 -right-8 w-24 h-24 rounded-full ${theme.accent} opacity-5 blur-2xl pointer-events-none`}
      />
    </div>
  )
}
