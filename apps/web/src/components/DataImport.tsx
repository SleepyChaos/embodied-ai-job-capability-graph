import { useCallback, useEffect, useRef, useState } from "react";

import { uploadXlsx, fetchImportBatches } from "../api";
import type { ImportResult, ImportBatch } from "../types";

export function DataImport() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [history, setHistory] = useState<ImportBatch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchImportBatches()
      .then((data) => setHistory(data.items))
      .catch(() => {});
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
      const importResult = await uploadXlsx(file);
      setResult(importResult);
      // Refresh history
      fetchImportBatches()
        .then((data) => setHistory(data.items))
        .catch(() => {});
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

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-foreground">数据导入</h2>
        <p className="mt-1 text-sm text-muted-foreground">
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
              : "border-border bg-muted/30 hover:border-primary/50"
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
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
              <svg className="h-6 w-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-foreground">{file.name}</p>
              <p className="text-sm text-muted-foreground">{formatFileSize(file.size)}</p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleReset();
              }}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              重新选择
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <svg className="h-6 w-6 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-foreground">拖拽 XLSX 文件到此处</p>
              <p className="text-sm text-muted-foreground">或点击选择文件</p>
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {/* Import Button */}
      {file && !result && (
        <button
          type="button"
          onClick={handleImport}
          disabled={importing}
          className="w-full rounded-lg bg-primary px-6 py-3 font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {importing ? "导入中..." : "开始导入"}
        </button>
      )}

      {/* Import Result */}
      {result && (
        <div className="space-y-4 rounded-lg border border-border bg-card p-6">
          <h3 className="text-lg font-medium text-foreground">导入结果</h3>

          {/* Statistics */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg bg-muted/50 p-3 text-center">
              <div className="text-2xl font-semibold text-foreground">{result.statistics.total}</div>
              <div className="text-xs text-muted-foreground">总计</div>
            </div>
            <div className="rounded-lg bg-success/10 p-3 text-center">
              <div className="text-2xl font-semibold text-success">{result.statistics.success}</div>
              <div className="text-xs text-muted-foreground">成功</div>
            </div>
            <div className="rounded-lg bg-warning/10 p-3 text-center">
              <div className="text-2xl font-semibold text-warning">{result.statistics.skipped}</div>
              <div className="text-xs text-muted-foreground">跳过</div>
            </div>
            <div className="rounded-lg bg-destructive/10 p-3 text-center">
              <div className="text-2xl font-semibold text-destructive">{result.statistics.failed}</div>
              <div className="text-xs text-muted-foreground">失败</div>
            </div>
          </div>

          {/* Capability Stats */}
          <div className="flex gap-4 text-sm text-muted-foreground">
            <span>新建能力: {result.statistics.capabilitiesCreated}</span>
            <span>新建别名: {result.statistics.aliasesCreated}</span>
          </div>

          {/* Errors */}
          {result.errors.length > 0 && (
            <div className="rounded-lg bg-destructive/5 p-3">
              <p className="mb-2 text-sm font-medium text-destructive">错误详情:</p>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {result.errors.slice(0, 5).map((err, i) => (
                  <li key={i}>• {err}</li>
                ))}
                {result.errors.length > 5 && (
                  <li className="text-muted-foreground">...还有 {result.errors.length - 5} 个错误</li>
                )}
              </ul>
            </div>
          )}

          <button
            type="button"
            onClick={handleReset}
            className="text-sm text-primary hover:underline"
          >
            继续导入其他文件
          </button>
        </div>
      )}

      {/* Import History */}
      {history.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-medium text-foreground">导入历史</h3>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">批次号</th>
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">文件名</th>
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">状态</th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">成功/总计</th>
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">时间</th>
                </tr>
              </thead>
              <tbody>
                {history.map((batch) => (
                  <tr key={batch.id} className="border-t border-border">
                    <td className="px-4 py-2 font-mono text-xs">{batch.batchCode}</td>
                    <td className="px-4 py-2">{batch.sourceFilename}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                          batch.status === "completed"
                            ? "bg-success/10 text-success"
                            : batch.status === "completed_with_errors"
                              ? "bg-warning/10 text-warning"
                              : "bg-destructive/10 text-destructive"
                        }`}
                      >
                        {batch.status === "completed" ? "完成" : batch.status === "completed_with_errors" ? "部分完成" : "失败"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {batch.successCount} / {batch.totalCount}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {new Date(batch.createdAt).toLocaleString("zh-CN")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
