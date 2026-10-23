"use client";

import { useEffect, useRef, useState } from "react";
import type { PDFDocumentLoadingTask, RenderTask, TextLayer } from "pdfjs-dist";
import "pdfjs-dist/web/pdf_viewer.css";

/** Render the exported bytes, independent of browser-native PDF plugin support. */
export default function PdfDocument({ src, title, thumbnail = false }: { src: string; title: string; thumbnail?: boolean }) {
  const root = useRef<HTMLDivElement>(null);
  const pages = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!root.current) return;
    const observer = new ResizeObserver(entries => setWidth(Math.floor(entries[0].contentRect.width)));
    observer.observe(root.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!src || !width) return;
    let disposed = false;
    let task: PDFDocumentLoadingTask | undefined;
    let rendering: RenderTask | undefined;
    let textRendering: TextLayer | undefined;
    const target = pages.current;
    setLoading(true); setError("");
    target?.replaceChildren();
    const timer = setTimeout(() => {
      void (async () => {
        const pdfjs = await import("pdfjs-dist");
        if (disposed) return;
        pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
        task = pdfjs.getDocument({ url: src, isEvalSupported: false });
        const pdf = await task.promise;
        for (let number = 1; number <= (thumbnail ? 1 : pdf.numPages); number++) {
          if (disposed) return;
          const page = await pdf.getPage(number);
          const scale = Math.max(80, width - (thumbnail ? 0 : 24)) / page.getViewport({ scale: 1 }).width;
          const viewport = page.getViewport({ scale });
          const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
          const sheet = document.createElement("div");
          sheet.className = "relative mx-auto mb-4 bg-white shadow-sm";
          sheet.style.width = `${viewport.width}px`; sheet.style.height = `${viewport.height}px`;
          sheet.setAttribute("aria-label", `Page ${number} of ${pdf.numPages}`);
          sheet.style.setProperty("--scale-factor", String(scale));
          const canvas = document.createElement("canvas");
          canvas.width = Math.ceil(viewport.width * pixelRatio); canvas.height = Math.ceil(viewport.height * pixelRatio);
          canvas.style.width = `${viewport.width}px`; canvas.style.height = `${viewport.height}px`;
          canvas.setAttribute("aria-hidden", "true");
          sheet.append(canvas);
          const context = canvas.getContext("2d");
          if (!context) throw new Error("Canvas rendering is unavailable.");
          rendering = page.render({ canvasContext: context, viewport, transform: [pixelRatio, 0, 0, pixelRatio, 0, 0] });
          await rendering.promise;
          if (disposed) return;
          if (!thumbnail) {
            const layer = document.createElement("div");
            layer.className = "textLayer";
            sheet.append(layer);
            textRendering = new pdfjs.TextLayer({ textContentSource: await page.getTextContent(), container: layer, viewport });
            await textRendering.render();
          }
          if (disposed) return;
          canvas.dataset.rendered = "true";
          target?.append(sheet);
        }
        if (!disposed) setLoading(false);
      })().catch(() => { if (!disposed) { setError("Preview could not be displayed. Open or download the PDF to view it."); setLoading(false); } });
    }, 100);
    return () => { disposed = true; clearTimeout(timer); rendering?.cancel(); textRendering?.cancel(); void task?.destroy().catch(() => undefined); target?.replaceChildren(); };
  }, [src, width, thumbnail]);
  return <div ref={root} role={thumbnail ? undefined : "region"} aria-label={title} data-pdf-url={src} aria-busy={loading} className={thumbnail ? "w-full" : "max-h-[860px] min-h-[240px] w-full overflow-auto rounded-xl border bg-[#e9ede5] py-3"}>
    {loading && <p role="status" className="p-3 text-xs text-muted">Drawing document…</p>}
    {error && <p role="alert" className="p-3 text-xs text-rose-800">{error}</p>}
    <div ref={pages} />
  </div>;
}
