"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import type { ReactNode } from "react";

type LeadCardProps = {
  id: number;
  children: ReactNode;
};

export default function LeadCard({
  id,
  children,
}: LeadCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: `lead-${id}`,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
    cursor: "grab",
    touchAction: "none" as const,
  };

  return (
   <div
  ref={setNodeRef}
  style={style}
  {...attributes}
>
  <div
    {...listeners}
    className="cursor-grab select-none border-b border-slate-200 px-4 py-2 text-center text-xs text-slate-400 active:cursor-grabbing"
    style={{ touchAction: "none" }}
  >
    <span>⠿ Arraste para mover</span>
  </div>

  <div className="p-4">
    {children}
  </div>
</div>
  );
}