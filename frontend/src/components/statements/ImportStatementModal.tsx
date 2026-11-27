import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Download, FileCode2, FileSpreadsheet, Upload, X } from 'lucide-react';
import { api, triggerBlobDownload } from '@/lib/api';
import type { AccountingStandard, OrgStatement, UnitScale } from '@/types/api';
import { BalanceCheckAssistant } from '@/components/statements/BalanceCheckAssistant';
import { Button, cn } from '@/components/ui/Primitives';

interface ImportStatementModalProps {
  companyId: number;
  companyName: string;
  open: boolean;
  onClose: () => void;
  onImported: (statement: OrgStatement) => void;
}

type ImportMode = 'xml' | 'excel';

export function ImportStatementModal({
  companyId,
  companyName,
  open,
  onClose,
  onImported,
}: ImportStatementModalProps) {
  const [mode, setMode] = useState<ImportMode>('xml');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [templateStandard, setTemplateStandard] = useState<
    'TT99_2025' | 'TT200_2014' | 'TT133_2016'
  >('TT99_2025');
  const [fiscalYearOverride, setFiscalYearOverride] = useState<string>('');
  const [unitScale, setUnitScale] = useState<UnitScale>(1);
  const [importedDraft, setImportedDraft] = useState<OrgStatement | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const downloadTemplateMutation = useMutation({
    mutationFn: () =>
      api.downloadBctcTemplate(templateStandard, new Date().getFullYear() - 1, 1_000_000),
    onSuccess: (blob) => {
      setErrorMessage(null);
      triggerBlobDownload(blob, `FinHealth_BCTC_${templateStandard}.xlsx`);
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể tải tệp mẫu Excel.'),
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error('Vui lòng chọn tệp trước khi tải lên.');
      const yearNum = fiscalYearOverride.trim() ? Number(fiscalYearOverride.trim()) : undefined;
      if (mode === 'xml') {
        return api.importHtkkXmlStatement(companyId, selectedFile, {
          fiscal_year: yearNum,
          unit_scale: unitScale,
        });
      }
      return api.importExcelStatement(companyId, selectedFile, {
        fiscal_year: yearNum,
        unit_scale: unitScale,
        accounting_standard: templateStandard as AccountingStandard,
      });
    },
    onSuccess: (statement) => {
      setErrorMessage(null);
      setImportedDraft(statement);
      onImported(statement);
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể đọc tệp báo cáo tài chính.'),
  });

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-[1px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-statement-title"
    >
      <div className="surface w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-xl">
        <div className="flex items-center justify-between gap-3 px-5 py-3.5 border-b border-[var(--border-subtle)]">
          <div>
            <h2 id="import-statement-title" className="text-sm font-semibold">
              Nhập BCTC từ XML HTKK / Excel chuẩn
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5 truncate">
              Doanh nghiệp: {companyName}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng hộp thoại nhập BCTC"
            className="p-1.5 rounded-[6px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4 text-xs">
          {/* Source Mode Switch */}
          <div className="grid grid-cols-2 gap-2" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'xml'}
              onClick={() => {
                setMode('xml');
                setSelectedFile(null);
                setUnitScale(1);
                setErrorMessage(null);
              }}
              className={cn(
                'p-3 rounded-[6px] border text-left flex items-center gap-2.5 cursor-pointer transition-colors',
                mode === 'xml'
                  ? 'border-[var(--accent-primary)] bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                  : 'border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]',
              )}
            >
              <FileCode2 className="h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <div>XML HTKK (Thuế)</div>
                <div className="text-[11px] font-normal opacity-80">TT99 / TT200 / TT133 (≤ 5 MB)</div>
              </div>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={mode === 'excel'}
              onClick={() => {
                setMode('excel');
                setSelectedFile(null);
                setUnitScale(1_000_000);
                setErrorMessage(null);
              }}
              className={cn(
                'p-3 rounded-[6px] border text-left flex items-center gap-2.5 cursor-pointer transition-colors',
                mode === 'excel'
                  ? 'border-[var(--accent-primary)] bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                  : 'border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]',
              )}
            >
              <FileSpreadsheet className="h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <div>Biểu mẫu Excel (.xlsx)</div>
                <div className="text-[11px] font-normal opacity-80">Tải file mẫu & nạp nhanh</div>
              </div>
            </button>
          </div>

          {/* Excel Template Downloader */}
          {mode === 'excel' ? (
            <div className="surface-subtle p-3.5 space-y-2.5 border border-[var(--border-subtle)]">
              <div className="font-medium text-[var(--text-primary)]">
                Bước 1: Tải biểu mẫu Excel chuẩn theo Thông tư
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  aria-label="Chọn chuẩn kế toán để tải mẫu Excel"
                  value={templateStandard}
                  onChange={(e) =>
                    setTemplateStandard(
                      e.target.value as 'TT99_2025' | 'TT200_2014' | 'TT133_2016',
                    )
                  }
                  className="h-8 px-2.5 bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-[6px]"
                >
                  <option value="TT99_2025">TT99/2025/TT-BTC</option>
                  <option value="TT200_2014">TT200/2014/TT-BTC</option>
                  <option value="TT133_2016">TT133/2016/TT-BTC</option>
                </select>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => downloadTemplateMutation.mutate()}
                  disabled={downloadTemplateMutation.isPending}
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />
                  Tải file mẫu Excel
                </Button>
              </div>
            </div>
          ) : null}

          {/* Upload Form */}
          <div className="space-y-3">
            <div>
              <label htmlFor="import-bctc-file" className="block font-medium mb-1">
                {mode === 'xml'
                  ? 'Chọn tệp XML xuất từ HTKK / phần mềm kế toán (.xml)'
                  : 'Bước 2: Chọn tệp Excel đã điền số liệu (.xlsx)'}
              </label>
              <input
                id="import-bctc-file"
                type="file"
                accept={mode === 'xml' ? '.xml,text/xml,application/xml' : '.xlsx'}
                onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                className="w-full p-2 bg-[var(--bg-canvas)] border border-dashed border-[var(--border-strong)] rounded-[6px] cursor-pointer"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="import-fiscal-year" className="block font-medium mb-1">
                  Năm tài chính (tùy chọn)
                </label>
                <input
                  id="import-fiscal-year"
                  type="number"
                  min={1990}
                  max={2100}
                  value={fiscalYearOverride}
                  onChange={(e) => setFiscalYearOverride(e.target.value)}
                  placeholder="Tự nhận diện từ tệp"
                  className="w-full h-9 px-2.5 font-mono bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px]"
                />
              </div>
              <div>
                <label htmlFor="import-unit-scale" className="block font-medium mb-1">
                  Đơn vị tiền tệ trong tệp
                </label>
                <select
                  id="import-unit-scale"
                  value={unitScale}
                  onChange={(e) => setUnitScale(Number(e.target.value) as UnitScale)}
                  className="w-full h-9 px-2.5 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px]"
                >
                  <option value={1}>Đồng (mặc định HTKK)</option>
                  <option value={1_000_000}>Triệu đồng</option>
                  <option value={1_000_000_000}>Tỷ đồng</option>
                </select>
              </div>
            </div>
          </div>

          {errorMessage ? (
            <div
              role="alert"
              className="p-3 rounded-[6px] bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)]"
            >
              {errorMessage}
            </div>
          ) : null}

          {importedDraft ? (
            <div className="space-y-3">
              <div
                role="status"
                className="p-3 rounded-[6px] bg-[var(--risk-low-bg)] text-[var(--risk-low-fg)]"
              >
                Đã nạp thành công bản nháp BCTC năm {importedDraft.fiscal_year} (chuẩn{' '}
                {importedDraft.accounting_standard}). Vui lòng kiểm tra cân đối trước khi chốt.
              </div>
              <BalanceCheckAssistant report={importedDraft.validation} />
            </div>
          ) : null}

          <div className="flex justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Đóng
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={!selectedFile || uploadMutation.isPending}
              onClick={() => uploadMutation.mutate()}
            >
              <Upload className="h-3.5 w-3.5" aria-hidden="true" />
              {uploadMutation.isPending ? 'Đang xử lý...' : 'Tải lên & Lưu nháp'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
