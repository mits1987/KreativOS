import React from 'react'

export default function BrainMark({ size = 28, fill = '#0F0F1A' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <line x1="20" y1="16" x2="32" y2="32" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="44" y1="16" x2="32" y2="32" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="14" y1="38" x2="32" y2="32" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="50" y1="38" x2="32" y2="32" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="32" y1="32" x2="32" y2="52" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <circle cx="20" cy="16" r="4.5" fill="#8B5CF6"/>
      <circle cx="44" cy="16" r="4.5" fill="#8B5CF6"/>
      <circle cx="14" cy="38" r="4"   fill="#10B981"/>
      <circle cx="50" cy="38" r="4"   fill="#10B981"/>
      <circle cx="32" cy="52" r="4"   fill="#6366F1"/>
      <circle cx="32" cy="32" r="8"   fill="#8B5CF6"/>
      <circle cx="32" cy="32" r="5"   fill={fill}/>
      <circle cx="32" cy="32" r="2.5" fill="#8B5CF6"/>
    </svg>
  )
}
