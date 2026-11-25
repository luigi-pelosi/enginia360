"use client"

import * as React from "react"

const margin = 16
const interactive = "button, a, input, select, textarea, [role='button'], [role='tab'], [role='checkbox'], [role='radio'], [role='switch'], [role='slider'], [role='combobox'], [role='textbox'], [contenteditable]:not([contenteditable='false']), [tabindex]:not([tabindex='-1'])"

type Gesture = {
  pointerId: number
  x: number
  y: number
  rect: DOMRect
  resize: boolean
}

// Geometria esterna condivisa: nessuna modifica alla struttura dei contenuti.
export function useDialogWindow() {
  const element = React.useRef<HTMLDivElement | null>(null)
  const gesture = React.useRef<Gesture | null>(null)

  React.useEffect(() => {
    const reset = () => {
      const node = element.current
      if (!node) return
      const active = gesture.current
      gesture.current = null
      if (active && node.hasPointerCapture(active.pointerId)) node.releasePointerCapture(active.pointerId)
      delete node.dataset.dialogFloating
      delete node.dataset.dialogResized
      for (const key of ["left", "top", "width", "height"]) node.style.removeProperty(`--dialog-${key}`)
    }
    // Il cambio viewport ripristina sempre il comportamento responsive originale.
    window.addEventListener("resize", reset)
    return () => {
      window.removeEventListener("resize", reset)
      gesture.current = null
    }
  }, [])

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.defaultPrevented || event.button !== 0 || event.isPrimary === false) return
    const target = event.target as HTMLElement
    const node = event.currentTarget
    if (target.closest("[data-slot='dialog-content'], [data-slot='alert-dialog-content']") !== node) return
    const resize = !!target.closest("[data-dialog-resize]")
    if (!resize && (!target.closest("[data-slot='dialog-header'], [data-slot='alert-dialog-header'], [data-slot='dialog-title'], [data-slot='alert-dialog-title']") || target.closest(interactive))) return
    element.current = node
    gesture.current = {pointerId: event.pointerId, x: event.clientX, y: event.clientY, rect: node.getBoundingClientRect(), resize}
    node.setPointerCapture(event.pointerId)
    event.preventDefault()
  }

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const active = gesture.current
    if (!active || active.pointerId !== event.pointerId) return
    const node = event.currentTarget
    const {rect} = active
    const dx = event.clientX - active.x
    const dy = event.clientY - active.y
    const availableWidth = window.innerWidth - margin * 2
    const availableHeight = window.innerHeight - margin * 2
    const width = Math.min(availableWidth, active.resize ? Math.max(Math.min(384, rect.width), rect.width + dx) : rect.width)
    const height = Math.min(availableHeight, active.resize ? Math.max(Math.min(320, rect.height), rect.height + dy) : rect.height)
    const left = Math.max(margin, Math.min(window.innerWidth - margin - width, rect.left + (active.resize ? 0 : dx)))
    const top = Math.max(margin, Math.min(window.innerHeight - margin - height, rect.top + (active.resize ? 0 : dy)))
    node.dataset.dialogFloating = ""
    if (active.resize) node.dataset.dialogResized = ""
    for (const [key, value] of Object.entries({left, top, width, height})) node.style.setProperty(`--dialog-${key}`, `${value}px`)
  }

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (gesture.current?.pointerId !== event.pointerId) return
    gesture.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const onScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const node = event.currentTarget
    if (event.target !== node) return
    node.style.setProperty("--dialog-scroll-x", `${node.scrollLeft}px`)
    node.style.setProperty("--dialog-scroll-y", `${node.scrollTop}px`)
  }

  return {onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp, onLostPointerCapture: onPointerUp, onScroll}
}
