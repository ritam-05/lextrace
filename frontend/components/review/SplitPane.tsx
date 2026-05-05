"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface SplitPaneProps {
  left: ReactNode;
  right: ReactNode;
}

export default function SplitPane({
  left,
  right,
}: SplitPaneProps) {
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(min-width: 1024px)");

    const updateViewport = (event?: MediaQueryListEvent): void => {
      setIsDesktop(event ? event.matches : mediaQuery.matches);
    };

    updateViewport();
    mediaQuery.addEventListener("change", updateViewport);

    return () => {
      mediaQuery.removeEventListener("change", updateViewport);
    };
  }, []);

  if (!isDesktop) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-6">
        <Tabs defaultValue="data" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="data">Extracted Data</TabsTrigger>
            <TabsTrigger value="pdf">PDF Source</TabsTrigger>
          </TabsList>
          <TabsContent value="data">{left}</TabsContent>
          <TabsContent value="pdf">{right}</TabsContent>
        </Tabs>
      </div>
    );
  }

  return (
    <PanelGroup direction="horizontal" className="h-screen">
      <Panel defaultSize={45} minSize={30}>
        {left}
      </Panel>
      <PanelResizeHandle className="w-1 bg-slate-200 hover:bg-slate-900 transition-colors" />
      <Panel defaultSize={55} minSize={30}>
        {right}
      </Panel>
    </PanelGroup>
  );
}
