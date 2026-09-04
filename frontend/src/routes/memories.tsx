import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Brain, Loader2, Search } from "lucide-react";
import { EmptyState, PageHeader } from "@/components/app/ui-bits";
import { Input } from "@/components/ui/input";
import { useContextBundle } from "@/lib/hooks";
import { formatRelative, memoryTypeLabel } from "@/lib/mappers";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/memories")({
  head: () => ({
    meta: [{ title: "Memories — ContextOS" }],
  }),
  component: MemoriesPage,
});

function MemoriesPage() {
  const contextQuery = useContextBundle();
  const [q, setQ] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "semantic" | "episodic">("all");

  const memories = useMemo(() => {
    const list = contextQuery.data?.memories ?? [];
    return list.filter((m) => {
      const type = memoryTypeLabel(m);
      if (typeFilter !== "all" && type !== typeFilter) return false;
      if (!q.trim()) return true;
      return m.content.toLowerCase().includes(q.toLowerCase());
    });
  }, [contextQuery.data?.memories, q, typeFilter]);

  return (
    <div className="mx-auto max-w-[980px] px-6 py-10 md:px-10 md:py-14">
      <PageHeader
        title="Memories"
        description="Long-term facts and episodes extracted from chat, with supersede support on the backend."
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter memories…"
            className="pl-8"
          />
        </div>
        {(["all", "semantic", "episodic"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs capitalize transition-colors",
              typeFilter === t
                ? "border-foreground/30 bg-surface-raised"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {contextQuery.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Loading memories…
        </div>
      ) : memories.length === 0 ? (
        <EmptyState
          icon={Brain}
          title="No memories yet"
          description="Chat with ContextOS and facts about you will land here via memory extraction."
        />
      ) : (
        <ul className="space-y-3">
          {memories.map((m) => (
            <li key={m.id} className="panel p-4">
              <div className="flex flex-wrap items-center gap-2 pb-2">
                <span className="rounded border px-1.5 py-0.5 text-mono-xs uppercase text-muted-foreground">
                  {memoryTypeLabel(m)}
                </span>
                {m.status && (
                  <span className="rounded border px-1.5 py-0.5 text-mono-xs uppercase text-muted-foreground">
                    {m.status}
                  </span>
                )}
                <span className="ml-auto text-mono-xs text-muted-foreground">
                  {formatRelative(m.created_at)}
                </span>
              </div>
              <p className="text-[14px] leading-relaxed">{m.content}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
