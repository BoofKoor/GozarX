import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  type DragStartEvent,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { clsx } from "clsx";
import { AlertCircle, EyeOff, GripVertical, Pencil, Plus, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ButtonEditor } from "@/components/buttons/ButtonEditor";
import { TelegramPreview } from "@/components/buttons/TelegramPreview";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { useButtons, useReorderButtons, useResetButton } from "@/hooks/useButtons";
import type { ButtonConfig, ReorderItem } from "@/types/api";

const SCREEN_NAMES: Record<string, string> = {
  main_menu: "منوی اصلی",
  landing: "صفحهٔ دریافت کانفیگ",
  help: "راهنما",
  config_delivered: "پس از تحویل کانفیگ",
  status: "وضعیت",
  settings: "تنظیمات",
  reminder: "یادآور",
  invite: "دعوت دوستان",
  location: "انتخاب لوکیشن",
  admin_menu: "منوی ادمین",
  admin_user_card: "کارت کاربر (ادمین)",
  confirm: "تأیید / لغو",
  admin_back: "بازگشت ادمین",
};

export function Buttons() {
  const { data: buttons = [], isLoading, isError, refetch } = useButtons();
  const [editing, setEditing] = useState<ButtonConfig | null>(null);

  const screens = useMemo(() => {
    const map = new Map<string, ButtonConfig[]>();
    for (const b of buttons) {
      const arr = map.get(b.screen) ?? [];
      arr.push(b);
      map.set(b.screen, arr);
    }
    return [...map.entries()];
  }, [buttons]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold">دکمه‌ها</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          متن (سه‌زبانه)، نمایش و چیدمان دکمه‌های ربات. برای جابه‌جایی، دکمه را بکش — حتی بین
          ردیف‌ها. دکمه‌های حیاتی (بازگشت/تأیید) قابل مخفی‌سازی نیستند.
        </p>
      </div>

      {editing && <ButtonEditor button={editing} onClose={() => setEditing(null)} />}

      {isError && buttons.length === 0 ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8 text-brand" />
        </div>
      ) : (
        screens.map(([screen, items]) => (
          <ScreenGroup key={screen} screen={screen} buttons={items} onEdit={(b) => setEditing(b)} />
        ))
      )}
    </div>
  );
}

function ScreenGroup({
  screen,
  buttons,
  onEdit,
}: {
  screen: string;
  buttons: ButtonConfig[];
  onEdit: (b: ButtonConfig) => void;
}) {
  const reorder = useReorderButtons();
  const reset = useResetButton();
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const rows = useMemo(() => {
    const byRow = new Map<number, ButtonConfig[]>();
    for (const b of buttons) {
      const arr = byRow.get(b.effective_row) ?? [];
      arr.push(b);
      byRow.set(b.effective_row, arr);
    }
    return [...byRow.entries()]
      .sort(([a], [b]) => a - b)
      .map(([row, btns]) => ({
        row,
        buttons: btns.sort((a, b) => a.effective_position - b.effective_position),
      }));
  }, [buttons]);

  const maxRow = rows.length ? Math.max(...rows.map((r) => r.row)) : -1;
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));
  const activeButton = activeKey ? buttons.find((b) => b.key === activeKey) : null;

  function handleDragEnd(event: DragEndEvent) {
    setActiveKey(null);
    const { active, over } = event;
    if (!over) return;
    const overId = String(over.id);
    const activeId = String(active.id);

    if (buttons.find((b) => b.key === activeId)?.is_critical) {
      toast.error("دکمهٔ حیاتی قابل جابه‌جایی نیست.");
      return;
    }

    let targetRow: number;
    let dropAtKey: string | null = null;
    if (overId.startsWith("rowzone-")) {
      targetRow = Number(overId.slice("rowzone-".length));
    } else if (overId === "newrow") {
      targetRow = maxRow + 1;
    } else {
      const overBtn = buttons.find((b) => b.key === overId);
      if (!overBtn) return;
      targetRow = overBtn.effective_row;
      dropAtKey = overId;
    }
    if (activeId === dropAtKey) return;

    const layout = rows.map((r) => ({
      row: r.row,
      keys: r.buttons.map((b) => b.key).filter((k) => k !== activeId),
    }));
    let target = layout.find((r) => r.row === targetRow);
    if (!target) {
      target = { row: targetRow, keys: [] };
      layout.push(target);
    }
    if (dropAtKey) {
      const idx = target.keys.indexOf(dropAtKey);
      target.keys.splice(idx < 0 ? target.keys.length : idx, 0, activeId);
    } else {
      target.keys.push(activeId);
    }

    const updates: ReorderItem[] = [];
    layout
      .filter((r) => r.keys.length > 0)
      .sort((a, b) => a.row - b.row)
      .forEach((r, rowIdx) =>
        r.keys.forEach((key, posIdx) => updates.push({ key, row_index: rowIdx, position: posIdx })),
      );
    reorder.mutate(updates, { onError: () => toast.error("جابه‌جایی ذخیره نشد.") });
  }

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-base font-bold">{SCREEN_NAMES[screen] ?? screen}</h2>
        <code className="text-xs text-slate-400" dir="ltr">
          {screen}
        </code>
      </div>

      <div className="mb-4">
        <TelegramPreview buttons={buttons} lang="fa" />
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={(e: DragStartEvent) => setActiveKey(String(e.active.id))}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={buttons.map((b) => b.key)} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {rows.map((r) => (
              <RowZone
                key={r.row}
                row={r.row}
                buttons={r.buttons}
                onEdit={onEdit}
                onReset={reset.mutate}
              />
            ))}
            <NewRowZone />
          </div>
        </SortableContext>
        <DragOverlay>
          {activeButton ? (
            <div className="rounded-lg border-2 border-brand bg-white px-2 py-2 text-sm shadow-lg dark:bg-slate-800">
              {activeButton.effective_label.fa}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </Card>
  );
}

function RowZone({
  row,
  buttons,
  onEdit,
  onReset,
}: {
  row: number;
  buttons: ButtonConfig[];
  onEdit: (b: ButtonConfig) => void;
  onReset: (key: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `rowzone-${row}` });
  return (
    <div
      ref={setNodeRef}
      className={clsx(
        "rounded-lg border p-2 transition",
        isOver
          ? "border-brand bg-brand/10"
          : "border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/50",
      )}
    >
      <div className="mb-1.5 text-[10px] font-mono text-slate-400">ردیف {row}</div>
      <div className="flex flex-col gap-1.5">
        {buttons.map((b) => (
          <DraggableButton
            key={b.key}
            button={b}
            onEdit={() => onEdit(b)}
            onReset={() => onReset(b.key)}
          />
        ))}
      </div>
    </div>
  );
}

function NewRowZone() {
  const { setNodeRef, isOver } = useDroppable({ id: "newrow" });
  return (
    <div
      ref={setNodeRef}
      className={clsx(
        "rounded-lg border-2 border-dashed p-3 text-center text-sm transition",
        isOver
          ? "border-emerald-500 bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30"
          : "border-slate-300 text-slate-400 dark:border-slate-700",
      )}
    >
      <span className="inline-flex items-center gap-1.5">
        <Plus className="h-4 w-4" />
        برای ساخت ردیف جدید، دکمه را اینجا بکش
      </span>
    </div>
  );
}

function DraggableButton({
  button,
  onEdit,
  onReset,
}: {
  button: ButtonConfig;
  onEdit: () => void;
  onReset: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: button.key,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : button.is_visible ? 1 : 0.45,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-2 dark:border-slate-700 dark:bg-slate-900"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-slate-400 hover:text-slate-600 active:cursor-grabbing"
        title="کشیدن برای جابه‌جایی"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm">{button.effective_label.fa}</span>
          {!button.is_visible && <EyeOff className="h-3 w-3 shrink-0 text-slate-400" />}
          {button.is_critical && (
            <AlertCircle className="h-3 w-3 shrink-0 text-amber-500" aria-label="حیاتی" />
          )}
          {button.customized && (
            <span className="shrink-0 rounded bg-brand/10 px-1 text-[10px] text-brand">سفارشی</span>
          )}
        </div>
        <code className="text-[10px] text-slate-400" dir="ltr">
          {button.key}
        </code>
      </div>
      <button
        onClick={onEdit}
        className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-brand dark:hover:bg-slate-800"
        title="ویرایش"
      >
        <Pencil className="h-3.5 w-3.5" />
      </button>
      {button.customized && (
        <button
          onClick={onReset}
          className="rounded p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-500 dark:hover:bg-rose-950/40"
          title="بازنشانی به پیش‌فرض"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
