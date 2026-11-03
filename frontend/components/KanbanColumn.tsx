"use client";

import { useDroppable } from "@dnd-kit/core";
import type { ReactNode } from "react";

type KanbanColumnProps = {
  id: string;
  children: ReactNode;
};

export default function KanbanColumn({
  id,
  children,
}: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({
    id,
  });

  return (
    <div
      ref={setNodeRef}
      className={`flex h-full min-h-[500px] flex-col rounded-2xl border p-5 transition-colors ${
        isOver
          ? "border-blue-500 bg-blue-50"
          : "border-slate-200 bg-white"
      }`}
    >
      {children}
    </div>
  );
}