"use client";

import * as React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/**
 * Server-rendered panels wrapped in a client tab shell. The content is built
 * on the server and handed over as React nodes, so switching tabs costs no
 * network round-trip and no analytics code ships to the browser.
 */
export function AnalysisTabs({
  tabs,
  defaultValue,
}: {
  tabs: Array<{ value: string; label: string; content: React.ReactNode }>;
  defaultValue?: string;
}) {
  const available = tabs.filter((t) => t.content);
  if (!available.length) return null;
  return (
    <Tabs defaultValue={defaultValue ?? available[0].value}>
      <TabsList className="scrollbar-thin overflow-x-auto px-2">
        {available.map((t) => (
          <TabsTrigger key={t.value} value={t.value}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {available.map((t) => (
        <TabsContent key={t.value} value={t.value} className="outline-none">
          {t.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}
