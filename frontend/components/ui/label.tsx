"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Label as LabelPrimitive } from "radix-ui"

function endsWithIndicator(children: React.ReactNode): boolean {
  if (typeof children === "string") return children.trimEnd().endsWith("*")
  if (Array.isArray(children)) return children.length > 0 && endsWithIndicator(children[children.length - 1])
  if (React.isValidElement<{ children?: React.ReactNode }>(children)) return endsWithIndicator(children.props.children)
  return false
}

function Label({
  className,
  children,
  asChild,
  required = false,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root> & { required?: boolean }) {
  const indicator = required && !endsWithIndicator(children) ? <span aria-hidden="true">*</span> : null
  const content = indicator && asChild && React.isValidElement<{ children?: React.ReactNode }>(children)
    ? React.cloneElement(children, undefined, children.props.children, indicator)
    : indicator ? <>{children}{indicator}</> : children

  return (
    <LabelPrimitive.Root
      asChild={asChild}
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    >
      {content}
    </LabelPrimitive.Root>
  )
}

export { Label }
