import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api";
import type { ImportHistoryItem, ImportResult } from "../types";

export function DataImport() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [history, setHistory] = useState<ImportHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.getImportHistory(controller.signal).then(setHistory).catch(() => {});
    return () => controller.abort();
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.endsWith(".xlsx")) {
      setFile(droppedFile);
      setError(null);
      setResult(null);
    } else {
      setError("请选择 .xlsx 格式的文件");
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.name.endsWith(".xlsx")) {
        setFile(selectedFile);
        setError(null);
        setResult(null);
      } else {
        setError("请选择 .xlsx 格式的文件");
      }
    }
  }, []);

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const importResult = await api.uploadXlsx(file);
      setResult(importResult);
      // Refresh history
      api.getImportHistory().then(setHistory).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入失败");
    } finally {
      setImporting(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-on-surface">数据导入</h2>
        <p className="mt-1 text-sm text-on-surface-variant">
          上传 XLSX 文件导入岗位数据，系统将自动解析、抽取能力并生成语义向量
        </p>
      </div>

      {/* Upload Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-colors ${
          dragging
            ? "border-primary bg-primary/5"
            : file
              ? "border-success bg-success/5"
              : "border-outline-variant bg-surface-container/30 hover:border-primary/50 hover:bg-surface-container/50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx"
          onChange={handleFileSelect}
          className="hidden"
        />

        {file ? (
          <div className="space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/20">
              <svg className="h-6 w-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <div className="font-medium text-on-surface">{file.name}</div>
              <div className="mt-1 text-sm text-on-surface-variant">
                {(file.size / 1024).toFixed(1)} KB
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleReset();
              }}
              className="text-sm text-on-surface-variant hover:text-on-surface"
            >
              移除文件
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface-container">
              <svg className="h-6 w-6 text-on-surface-variant" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div>
              <div className="font-medium text-on-surface">
                拖拽 XLSX 文件到此处，或点击选择文件
              </div>
              <div className="mt-1 text-sm text-on-surface-variant">
                仅支持 .xlsx 格式
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-error/30 bg-error/10 p-4 text-sm text-error">
          {error}
        </div>
      )}

      {/* Import Button */}
      {file && !result && (
        <div className="flex justify-center">
          <button
            onClick={handleImport}
            disabled={importing}
            className="rounded-lg bg-primary px-8 py-3 font-medium text-on-primary shadow-card transition-shadow hover:shadow-float disabled:opacity-50"
          >
            {importing ? "导入中..." : "开始导入"}
          </button>
        </div>
      )}

      {/* Import Result */}
      {result && (
        <div className="space-y-6">
          {/* Stats Cards */}
          <div className="grid gap-4 sm:grid-cols-4">
            <StatCard label="总行数" value={result.total_rows} color="default" />
            <StatCard label="成功导入" value={result.imported} color="success" />
            <StatCard label="跳过" value={result.skipped} color="warning" />
            <StatCard label="失败" value={result.failed} color="error" />
          </div>

          {/* Additional Stats */}
          <div className="flex gap-4 rounded-lg bg-surface-container/50 p-4">
            <div className="text-sm">
              <span className="text-on-surface-variant">新建能力：</span>
              <span className="font-medium text-on-surface">{result.new_capabilities_created}</span>
            </div>
            <div className="text-sm">
              <span className="text-on-surface-variant">新建别名：</span>
              <span className="font-medium text-on-surface">{result.new_aliases_created}</span>
            </div>
          </div>

          {/* Detail Table */}
          {result.details.length > 0 && (
            <div className="rounded-lg border border-outline-variant bg-surface">
              <div className="border-b border-outline-variant p-4">
                <h3 className="font-medium text-on-surface">导入详情</h3>
              </div>
              <div className="max-h-80 overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-container">
                    <tr className="text-left text-on-surface-variant">
                      <th className="px-4 py-3 font-medium">行号</th>
                      <th className="px-4 py-3 font-medium">公司</th>
                      <th className="px-4 py-3 font-medium">岗位</th>
                      <th className="px-4 py-3 font-medium">状态</th>
                      <th className="px-4 py-3 font-medium">能力数</th>
                      <th className="px-4 py-3 font-medium">说明</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.details.map((detail, i) => (
                      <tr key={i} className="border-t border-outline-variant/50">
                        <td className="px-4 py-2 text-on-surface-variant">{detail.row}</td>
                        <td className="px-4 py-2 text-on-surface">{detail.company}</td>
                        <td className="px-4 py-2 text-on-surface">{detail.position}</td>
                        <td className="px-4 py-2">
                          <StatusBadge status={detail.status} />
                        </td>
                        <td className="px-4 py-2 text-on-surface">{detail.capabilities_extracted}</td>
                        <td className="px-4 py-2 text-on-surface-variant">{detail.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Reset Button */}
          <div className="flex justify-center">
            <button
              onClick={handleReset}
              className="rounded-lg border border-outline-variant px-6 py-2 text-sm font-medium text-on-surface hover:bg-surface-container"
            >
              继续导入其他文件
            </button>
          </div>
        </div>
      )}

      {/* Import History */}
      {history.length > 0 && !result && (
        <div className="rounded-lg border border-outline-variant bg-surface">
          <div className="border-b border-outline-variant p-4">
            <h3 className="font-medium text-on-surface">导入历史</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-on-surface-variant">
                <th className="px-4 py-3 font-medium">时间</th>
                <th className="px-4 py-3 font-medium">文件名</th>
                <th className="px-4 py-3 font-medium">导入数</th>
                <th className="px-4 py-3 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.id} className="border-t border-outline-variant/50">
                  <td className="px-4 py-2 text-on-surface-variant">
                    {new Date(item.imported_at).toLocaleString("zh-CN")}
                  </td>
                  <td className="px-4 py-2 text-on-surface">{item.filename}</td>
                  <td className="px-4 py-2 text-on-surface">
                    {item.imported} / {item.total_rows}
                  </td>
                  <td className="px-4 py-2">
                    <HistoryStatusBadge status={item.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorClasses = {
    default: "bg-surface-container/50 text-on-surface",
    success: "bg-success/10 text-success",
    warning: "bg-warning/10 text-warning",
    error: "bg-error/10 text-error",
  }[color] ?? "bg-surface-container/50 text-on-surface";

  return (
    <div className={`rounded-lg p-4 ${colorClasses.split(" ")[0]}`}>
      <div className="text-sm text-on-surface-variant">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${colorClasses.split(" ")[1]}`}>{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const classes = {
    imported: "bg-success/20 text-success",
    skipped: "bg-warning/20 text-warning",
    failed: "bg-error/20 text-error",
  }[status] ?? "bg-surface-container text-on-surface-variant";

  const labels = { imported: "成功", skipped: "跳过", failed: "失败" };

  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${classes}`}>
      {labels[status as keyof typeof labels] ?? status}
    </span>
  );
}

function HistoryStatusBadge({ status }: { status: string }) {
  const classes = {
    completed: "bg-success/20 text-success",
    partial: "bg-warning/20 text-warning",
    failed: "bg-error/20 text-error",
  }[status] ?? "bg-surface-container text-on-surface-variant";

  const labels = { completed: "完成", partial: "部分成功", failed: "失败" };

  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${classes}`}>
      {labels[status as keyof typeof labels] ?? status}
    </span>
  );
}
