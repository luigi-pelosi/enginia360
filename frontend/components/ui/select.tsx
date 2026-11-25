"use client"

import * as React from "react"
import { useTranslations } from "next-intl"
import { CheckIcon, ChevronDownIcon } from "lucide-react"
import { Popover, Select as SelectPrimitive } from "radix-ui"
import { cn } from "@/lib/utils"
import * as Ordinary from "./select-ordinary"

type Option = { value: string; label: React.ReactNode; text: string; disabled?: boolean }
type State = {
  value: string; open: boolean; disabled?: boolean; required?: boolean
  query: string; setQuery: (query: string) => void
  active: string | null; setActive: (value: string | null) => void
  options: Option[]; visible: Option[]; choose: (value: string) => void
  setOpen: (open: boolean) => void; id: string
  trigger: React.RefObject<HTMLButtonElement | null>; invalid: boolean
}
const Context = React.createContext<State | null>(null)
const fold = (text: string) => text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase()
function textOf(node: React.ReactNode): string {
  return React.Children.toArray(node).map(child => React.isValidElement<{children?: React.ReactNode}>(child) ? textOf(child.props.children) : String(child ?? "")).join("")
}
// Le opzioni derivano dalla dichiarazione completa, non dal DOM montato o filtrato.
function collect(children: React.ReactNode): Option[] {
  return React.Children.toArray(children).flatMap(child => {
    if (!React.isValidElement<React.ComponentProps<typeof SelectItem>>(child)) return []
    if (child.type === SelectItem) return [{value: child.props.value, label: child.props.children, text: `${textOf(child.props.children)} ${child.props.textValue ?? ""}`, disabled: child.props.disabled}]
    return collect(child.props.children)
  })
}
function Select({searchable = true, ...props}: React.ComponentProps<typeof SelectPrimitive.Root> & {searchable?: boolean}) {
  return searchable ? <SearchSelect {...props} /> : <Context.Provider value={null}><Ordinary.Select {...props} /></Context.Provider>
}
function SearchSelect({children, value: controlledValue, defaultValue = "", onValueChange, open: controlledOpen, defaultOpen = false, onOpenChange, disabled, required, name, form, dir}: React.ComponentProps<typeof SelectPrimitive.Root>) {
  const [localValue, setLocalValue] = React.useState(defaultValue)
  const [localOpen, setLocalOpen] = React.useState(defaultOpen)
  const [query, setQueryState] = React.useState("")
  const [active, setActive] = React.useState<string | null>(null)
  const [invalidValue, setInvalidValue] = React.useState<string | null>(null)
  const native = React.useRef<HTMLSelectElement>(null)
  const t = useTranslations("errors")
  const trigger = React.useRef<HTMLButtonElement>(null)
  const id = React.useId()
  const value = controlledValue ?? localValue
  const open = controlledOpen ?? localOpen
  const invalid = invalidValue === value && !!required && !disabled
  React.useEffect(() => {setInvalidValue(null)}, [value, required, disabled])
  React.useEffect(() => {
    const owner = native.current?.form
    if (!owner) return
    const reset = () => setInvalidValue(null)
    owner.addEventListener("reset", reset)
    return () => owner.removeEventListener("reset", reset)
  }, [form])
  const options = collect(children).filter(option => !required || option.value !== "__none__")
  const visible = options.filter(option => fold(`${option.text} ${option.value}`).includes(fold(query)))
  const setQuery = (next: string) => {setQueryState(next); setActive(null)}
  const setOpen = (next: boolean) => {
    if (disabled && next) return
    if (!next) {setQueryState(""); setActive(null)}
    if (next !== open) {setLocalOpen(next); onOpenChange?.(next)}
  }
  // Azzera la ricerca anche quando il componente proprietario chiude il popup controllato.
  React.useEffect(() => {if (!open) {setQueryState(""); setActive(null)}}, [open])
  const choose = (next: string) => {
    const option = options.find(option => option.value === next)
    if (disabled || !option || option.disabled) return
    if (next !== value) {if (controlledValue === undefined) setInvalidValue(null); setLocalValue(next); onValueChange?.(next)}
    setOpen(false)
  }
  const state: State = {value, open, disabled, required, query, setQuery, active, setActive, options, visible, choose, setOpen, id, trigger, invalid}
  return <Context.Provider value={state}>
    <Popover.Root open={open && !disabled} onOpenChange={setOpen} modal={false}>
      {children}
    </Popover.Root>
    {(name || required) && <select ref={native} aria-hidden="true" tabIndex={-1} className="sr-only" name={name} form={form} dir={dir} required={required} disabled={disabled} value={value}
      onChange={event => choose(event.target.value)} onInvalid={event => {
        event.preventDefault()
        setInvalidValue(value)
        const target = event.currentTarget
        const firstInvalid = target?.form && Array.from(target.form.elements).find(element => {
          const control = element as HTMLInputElement
          return control.willValidate && !control.validity.valid
        })
        if (!firstInvalid || firstInvalid === target) trigger.current?.focus()
      }}>
      <option value="" />
      {value && value !== "__none__" && !options.some(option => option.value === value) && <option value={value}>{value}</option>}
      {options.map(option => <option key={option.value} value={option.value} disabled={option.disabled}>{textOf(option.label)}</option>)}
    </select>}
    {invalid && <span id={`${id}-error`} data-slot="select-error" className="text-sm text-destructive">{t("field_required")}</span>}
  </Context.Provider>
}
function SelectTrigger({className, size = "default", children, ref, onKeyDown, disabled, "aria-describedby": describedBy, "aria-invalid": ariaInvalid, ...props}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {size?: "sm" | "default"}) {
  const state = React.useContext(Context)
  if (!state) return <Ordinary.SelectTrigger aria-describedby={describedBy} aria-invalid={ariaInvalid} className={className} size={size} ref={ref} disabled={disabled} onKeyDown={onKeyDown} {...props}>{children}</Ordinary.SelectTrigger>
  return <Popover.Trigger asChild><button {...props} type="button" ref={node => {state.trigger.current = node; if (typeof ref === "function") ref(node); else if (ref) ref.current = node}}
    role="combobox" aria-invalid={state.invalid || ariaInvalid} aria-describedby={[describedBy, state.invalid ? `${state.id}-error` : undefined].filter(Boolean).join(" ") || undefined} aria-haspopup="listbox" aria-expanded={state.open && !state.disabled} aria-controls={`${state.id}-list`} aria-required={state.required}
    disabled={state.disabled || disabled} data-slot="select-trigger" data-size={size} data-placeholder={!state.value ? "" : undefined}
    className={cn("flex min-w-0 items-center justify-between gap-2 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-[placeholder]:text-muted-foreground data-[size=default]:h-9 data-[size=sm]:h-8 dark:bg-input/30 [&_svg]:shrink-0", className)}
    onKeyDown={event => {onKeyDown?.(event); if (!event.defaultPrevented && !state.disabled && (event.key === "ArrowDown" || event.key === "ArrowUp")) {event.preventDefault(); state.setOpen(true)}}}>
    {children}<ChevronDownIcon className="size-4 shrink-0 opacity-50" />
  </button></Popover.Trigger>
}
function SelectValue({children, placeholder, ...props}: React.ComponentProps<typeof SelectPrimitive.Value>) {
  const state = React.useContext(Context)
  const t = useTranslations("app")
  if (!state) return <Ordinary.SelectValue placeholder={placeholder} {...props}>{children}</Ordinary.SelectValue>
  return <span {...props} data-slot="select-value" className="block min-w-0 truncate">{children ?? state.options.find(option => option.value === state.value)?.label ?? (state.required && state.value === "__none__" ? placeholder ?? t("empty") : state.value || placeholder)}</span>
}
function SelectContent({children, className, position: _position, align = "center", onEscapeKeyDown, onCloseAutoFocus, ...props}: React.ComponentProps<typeof SelectPrimitive.Content>) {
  const state = React.useContext(Context)
  const t = useTranslations("app")
  const input = React.useRef<HTMLInputElement>(null)
  React.useEffect(() => {
    if (state?.active) input.current?.ownerDocument.getElementById(`${state.id}-${state.active}`)?.scrollIntoView({block: "nearest"})
  }, [state?.active, state?.id])
  if (!state) return <Ordinary.SelectContent className={className} align={align} position={_position} onEscapeKeyDown={onEscapeKeyDown} onCloseAutoFocus={onCloseAutoFocus} {...props}>{children}</Ordinary.SelectContent>
  if (!state.open || state.disabled) return null
  const keyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {event.preventDefault(); event.stopPropagation(); state.setOpen(false); return}
    if (event.key === "Tab") {state.setOpen(false); return}
    if (event.key === "Enter") {event.preventDefault(); event.stopPropagation(); if (state.active) state.choose(state.active); return}
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return
    event.preventDefault(); event.stopPropagation()
    const enabled = state.visible.filter(option => !option.disabled)
    if (!enabled.length) return
    const index = enabled.findIndex(option => option.value === state.active)
    const next = index < 0 ? (event.key === "ArrowUp" ? enabled.length - 1 : 0) : (index + (event.key === "ArrowUp" ? -1 : 1) + enabled.length) % enabled.length
    state.setActive(enabled[next].value)
  }
  return <Popover.Portal><Popover.Content {...props} role="presentation" data-slot="select-content" align={align} sideOffset={4}
    className={cn("z-50 flex max-h-[min(24rem,var(--radix-popover-content-available-height))] w-[var(--radix-popover-trigger-width)] min-w-[8rem] max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md", className)}
    onOpenAutoFocus={event => {event.preventDefault(); input.current?.focus()}}
    onCloseAutoFocus={event => {onCloseAutoFocus?.(event); if (!event.defaultPrevented) {event.preventDefault(); state.trigger.current?.focus()}}}
    onEscapeKeyDown={event => {event.stopPropagation(); onEscapeKeyDown?.(event)}}>
    <div className="shrink-0 border-b p-2"><input ref={input} type="text" data-slot="select-search" aria-label={t("search")} placeholder={t("search")} value={state.query}
      aria-controls={`${state.id}-list`} aria-activedescendant={state.active ? `${state.id}-${state.active}` : undefined} autoComplete="off"
      className="h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 sm:text-sm"
      onChange={event => state.setQuery(event.target.value)} onKeyDown={keyDown} /></div>
    <div id={`${state.id}-list`} role="listbox" aria-label={t("search")} className="min-h-0 overflow-y-auto overscroll-contain p-1">{children}</div>
    {!state.visible.length && <div role="status" data-slot="select-empty" className="px-3 py-4 text-center text-sm text-muted-foreground">{t("empty")}</div>}
  </Popover.Content></Popover.Portal>
}
function SelectItem({children, value, disabled, className, textValue: _textValue, onClick, onPointerMove, ...props}: React.ComponentProps<typeof SelectPrimitive.Item>) {
  const state = React.useContext(Context)
  if (!state) return <Ordinary.SelectItem value={value} disabled={disabled} className={className} textValue={_textValue} onClick={onClick} onPointerMove={onPointerMove} {...props}>{children}</Ordinary.SelectItem>
  if (!state.visible.some(option => option.value === value)) return null
  return <div {...props} id={`${state.id}-${value}`} role="option" aria-selected={value === state.value} aria-disabled={disabled || state.disabled || undefined}
    data-slot="select-item" data-value={value} data-disabled={disabled ? "" : undefined} data-highlighted={state.active === value ? "" : undefined} tabIndex={-1}
    className={cn("relative flex w-full cursor-default items-center gap-2 rounded-sm py-1.5 pr-8 pl-2 text-sm outline-none select-none break-words data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[disabled]:opacity-50", className)}
    onPointerDown={event => {props.onPointerDown?.(event); event.preventDefault()}}
    onPointerMove={event => {onPointerMove?.(event); if (!disabled && !state.disabled) state.setActive(value)}}
    onClick={event => {onClick?.(event); if (!event.defaultPrevented) state.choose(value)}}>
    {children}{value === state.value && <CheckIcon className="absolute top-1/2 right-2 size-4 -translate-y-1/2" />}
  </div>
}
function SelectGroup(props: React.ComponentProps<typeof SelectPrimitive.Group>) {return React.useContext(Context) ? <div {...props} role="group" data-slot="select-group" /> : <Ordinary.SelectGroup {...props} />}
function SelectLabel({className, ...props}: React.ComponentProps<typeof SelectPrimitive.Label>) {return React.useContext(Context) ? <div {...props} data-slot="select-label" className={cn("px-2 py-1.5 text-xs text-muted-foreground", className)} /> : <Ordinary.SelectLabel {...props} className={className} />}
function SelectSeparator({className, ...props}: React.ComponentProps<typeof SelectPrimitive.Separator>) {return React.useContext(Context) ? <div {...props} role="separator" data-slot="select-separator" className={cn("-mx-1 my-1 h-px bg-border", className)} /> : <Ordinary.SelectSeparator {...props} className={className} />}
function SelectScrollUpButton(props: React.ComponentProps<typeof SelectPrimitive.ScrollUpButton>) {return React.useContext(Context) ? null : <Ordinary.SelectScrollUpButton {...props} />}
function SelectScrollDownButton(props: React.ComponentProps<typeof SelectPrimitive.ScrollDownButton>) {return React.useContext(Context) ? null : <Ordinary.SelectScrollDownButton {...props} />}
export {Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectScrollDownButton, SelectScrollUpButton, SelectSeparator, SelectTrigger, SelectValue}
