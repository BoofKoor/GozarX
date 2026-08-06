import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  type DragStartEvent,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { clsx } from "clsx";
import { AlertCircle, EyeOff, GripVertical, Pencil, Plus, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ButtonEditor } from "@/components/buttons/ButtonEditor";
import { TelegramPreview } from "@/components/buttons/TelegramPreview";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { useButtons, useReorderButtons, useResetButton } from "@/hooks/useButtons";
import { useI18n, type MessageKey } from "@/i18n";
import { formatNumber } from "@/lib/format";
import type { ButtonConfig, ReorderItem } from "@/types/api";

/** The screens the bot renders keyboards for. An unknown screen falls back to its raw key. */
const SCREENS = [
  "main_menu",
  "landing",
  "help",
  "config_delivered",
  "status",
  "settings",
  "reminder",
  "invite",
  "location",
  "admin_menu",
  "admin_user_card",
  "confirm",
  "admin_back",
] as const;

function screenKey(screen: string): MessageKey | null {
  return (SCREENS as readonly string[]).includes(screen)
    ? (`btn.screen.${screen}` as MessageKey)
    : null;
}

export function Buttons() {
  const { t } = useI18n();
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
      <PageHeader title={t("btn.title")} sub={t("btn.sub")} />

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
  const { t, locale } = useI18n();
  const label = screenKey(screen);
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
  // Passing an explicit list REPLACES dnd-kit's defaults rather than adding to them, so naming only
  // the pointer sensor dropped the keyboard one — and reordering is the entire job of this page.
  // The handle already announced itself as sortable (`aria-roledescription` comes from dnd-kit's
  // `attributes`), so a keyboard operator was told the row could be moved and then found that
  // nothing moved it. `sortableKeyboardCoordinates` is what makes the arrows step between ITEMS
  // instead of nudging by a fixed pixel amount.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const activeButton = activeKey ? buttons.find((b) => b.key === activeKey) : null;

  function handleDragEnd(event: DragEndEvent) {
    setActiveKey(null);
    const { active, over } = event;
    if (!over) return;
    const overId = String(over.id);
    const activeId = String(active.id);

    if (buttons.find((b) => b.key === activeId)?.is_critical) {
      toast.error(t("btn.criticalDrag"));
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
    reorder.mutate(updates, { onError: () => toast.error(t("btn.reorderFailed")) });
  }

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-base font-bold">{label ? t(label) : screen}</h2>
        <code className="font-mono text-xs text-content-subtle" dir="ltr">
          {screen}
        </code>
      </div>

      <div className="mb-4 max-w-3xl">
        {/* Preview in the language the operator is reading the panel in — checking an English
            label against a Persian preview is the one thing this control cannot do. */}
        <TelegramPreview buttons={buttons} lang={locale} />
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={(e: DragStartEvent) => setActiveKey(String(e.active.id))}
        onDragEnd={handleDragEnd}
      >
        {/* Capped, not full-bleed. A row puts its name at the start edge and its edit/reset icons
            at the end, so on a 1440 screen the control for a row sat ~1400px from the row it acted
            on — a full horizontal traverse per edit, with only vertical alignment saying which
            pencil belonged to which button. */}
        <SortableContext items={buttons.map((b) => b.key)} strategy={verticalListSortingStrategy}>
          <div className="max-w-3xl space-y-2">
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
            <div className="rounded-lg border-2 border-brand bg-surface px-2 py-2 text-sm shadow-lg">
              {activeButton.effective_label[locale]}
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
  const { t } = useI18n();
  const { setNodeRef, isOver } = useDroppable({ id: `rowzone-${row}` });
  return (
    <div
      ref={setNodeRef}
      className={clsx(
        "rounded-lg border p-2 transition",
        isOver ? "border-brand bg-brand/15" : "border-line bg-surface-sunken",
      )}
    >
      <div className="mb-1.5 font-mono text-[10px] text-content-subtle">
        {t("btn.row", { n: formatNumber(row + 1) })}
      </div>
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
  const { t } = useI18n();
  const { setNodeRef, isOver } = useDroppable({ id: "newrow" });
  return (
    <div
      ref={setNodeRef}
      className={clsx(
        "rounded-lg border-2 border-dashed p-3 text-center text-sm transition",
        isOver
          ? "border-success-500 bg-success-500/15 text-success-700"
          : "border-line-strong text-content-subtle",
      )}
    >
      <span className="inline-flex items-center gap-1.5">
        <Plus className="h-4 w-4" />
        {t("btn.newRow")}
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
  const { t, locale } = useI18n();
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
      className="flex items-center gap-2 rounded-lg border border-line bg-surface px-2 py-2"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-content-subtle hover:text-content-muted active:cursor-grabbing"
        title={t("btn.drag")}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm">{button.effective_label[locale]}</span>
          {!button.is_visible && <EyeOff className="h-3 w-3 shrink-0 text-content-subtle" />}
          {button.is_critical && (
            <AlertCircle
              className="h-3 w-3 shrink-0 text-warning-600"
              aria-label={t("btn.critical")}
            />
          )}
          {button.customized && (
            <span className="shrink-0 rounded bg-brand/20 px-1 text-[10px] text-brand-700">
              {t("btn.custom")}
            </span>
          )}
        </div>
        <code className="text-[10px] text-content-subtle" dir="ltr">
          {button.key}
        </code>
      </div>
      <button
        onClick={onEdit}
        className="rounded p-1.5 text-content-subtle hover:bg-surface-hover hover:text-brand"
        title={t("btn.edit")}
      >
        <Pencil className="h-3.5 w-3.5" />
      </button>
      {button.customized && (
        <button
          onClick={onReset}
          className="rounded p-1.5 text-content-subtle hover:bg-danger-500/15 hover:text-danger-700"
          title={t("btn.reset")}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
