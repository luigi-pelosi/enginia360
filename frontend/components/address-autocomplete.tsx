"use client";
import {useEffect, useRef, useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import {Input} from "@/components/ui/input";
import {api} from "@/lib/api";

export type AddressField = "address" | "city" | "province" | "postal_code" | "region";
export type AddressSuggestion = {label: string; address?: string; city?: string; province?: string; postalCode?: string; countryCode?: string; region?: string | null};
export function addressSelection(old: Record<string, unknown>, field: AddressField, item: AddressSuggestion) {
  const next = {...old};
  const mapping = {country_code: item.countryCode, province: item.province, city: item.city, postal_code: item.postalCode, address: item.address};
  const order = Object.keys(mapping) as (keyof typeof mapping)[];
  // Il cambio del contesto invalida i componenti discendenti non restituiti.
  // Anche una nuova strada nella stessa città non conserva un CAP precedente.
  let changed = false;
  for (const key of order) {
    const value = mapping[key];
    if (value) {
      if (String(old[key] ?? "") !== value) changed = true;
      next[key] = value;
    } else if (changed || (order.indexOf(key) > order.indexOf(field as keyof typeof mapping) && field !== "postal_code")) next[key] = "";
  }
  if (field === "address" && !item.postalCode) next.postal_code = "";
  if (item.region != null) next.region = item.region;
  // Il catalogo locale completa la località, non sostituisce la strada manuale.
  if (item.region != null && !item.address) next.address = old.address ?? "";
  return next;
}
export function AddressAutocomplete({id, field, value, context, scope, disabled, required, onChange, onSelect}: {
  id: string; field: AddressField; value: string; context: Record<string, unknown>; scope: (path: string) => string;
  disabled: boolean; required: boolean; onChange: (text: string) => void; onSelect: (item: AddressSuggestion) => void;
}) {
  const locale = useLocale(), t = useTranslations("app");
  const [items, setItems] = useState<AddressSuggestion[]>([]), [focused, setFocused] = useState(false),
    [active, setActive] = useState(-1), [error, setError] = useState(false), [open, setOpen] = useState(true);
  const generation = useRef(0), controller = useRef<AbortController | null>(null), selected = useRef<string | null>(null);
  const listId = `${id}-suggestions`;
  const country = String(context.country_code ?? ""), city = String(context.city ?? ""), province = String(context.province ?? "");
  useEffect(() => {
    const current = ++generation.current;
    controller.current?.abort();
    setItems([]); setActive(-1); setError(false);
    if (field === "region" || disabled || !focused || !open || value.trim().length < 3 || value.length > 200 || selected.current === value) return;
    const abort = new AbortController(); controller.current = abort;
    const timer = setTimeout(async () => {
      const query = new URLSearchParams({field, text: value.trim(), language: locale === "en" ? "en" : "it"});
      if (country) query.set("countryCode", country);
      if (city && field !== "city") query.set("city", city);
      if (province && field !== "province") query.set("province", province);
      try {
        const data = await api<{items: AddressSuggestion[]; attribution?: string}>(scope(`/addresses/autocomplete?${query}`), "GET", undefined, {signal: abort.signal});
        if (!abort.signal.aborted && current === generation.current) setItems(data.items.slice(0, 5));
      } catch {
        if (!abort.signal.aborted && current === generation.current) setError(true);
      }
    }, 350);
    return () => {clearTimeout(timer); abort.abort();};
  }, [value, field, country, city, province, locale, scope, focused, disabled, open]);
  const visible = focused && open && !disabled && items.length > 0;
  function choose(item: AddressSuggestion) {
    if (disabled) return;
    generation.current++; controller.current?.abort();
    selected.current = field === "postal_code" ? item.postalCode ?? "" : item[field] ?? "";
    setOpen(false); setItems([]); setActive(-1); onSelect(item);
  }
  return <div className="relative" onBlur={e => {if (!e.currentTarget.contains(e.relatedTarget)) {setFocused(false); generation.current++; controller.current?.abort();}}}>
    <Input id={id} value={value} disabled={disabled} required={required} maxLength={200} autoComplete="off"
      role="combobox" aria-autocomplete="list" aria-expanded={visible} aria-controls={visible ? listId : undefined}
      aria-activedescendant={visible && active >= 0 ? `${listId}-${active}` : undefined} aria-describedby={error ? `${id}-error` : undefined}
      onFocus={() => {if (!disabled) {setFocused(true); setOpen(true);}}}
      onChange={e => {if (disabled) return; generation.current++; controller.current?.abort(); selected.current = null; setOpen(true); setItems([]); onChange(e.target.value);}}
      onKeyDown={e => {
        if (disabled) return;
        if (e.key === "Escape") {e.preventDefault(); e.stopPropagation(); setOpen(false); generation.current++; controller.current?.abort();}
        if ((e.key === "ArrowDown" || e.key === "ArrowUp") && items.length) {
          e.preventDefault(); setOpen(true); setActive(old => old < 0 ? (e.key === "ArrowDown" ? 0 : items.length - 1) : (old + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length);
        }
        if (e.key === "Enter" && visible && active >= 0) {e.preventDefault(); choose(items[active]);}
      }} />
    {visible && <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
      <ul id={listId} role="listbox" aria-label={t("addressSuggestions")}>
        {items.map((item, index) => <li key={index} id={`${listId}-${index}`} role="option" aria-selected={active === index}
          className={`cursor-pointer rounded-sm px-2 py-2 text-sm ${active === index ? "bg-accent" : ""}`}
          onMouseDown={e => e.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => choose(item)}>{item.label}</li>)}
      </ul>
    </div>}
    {error && focused && <p id={`${id}-error`} role="status" className="absolute top-full right-0 left-0 z-50 mt-1 rounded-md border bg-popover p-2 text-sm text-popover-foreground shadow-md">{t("addressUnavailable")}</p>}
  </div>;
}
