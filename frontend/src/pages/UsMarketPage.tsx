import { Globe2 } from 'lucide-react';
import { ScreenerPage } from './ScreenerPage';

export function UsMarketPage() {
  return (
    <div className="space-y-4 animate-view min-w-0">
      <div className="px-4 py-2.5 rounded-[3px] border border-[var(--accent-border)] bg-[var(--accent-soft)] flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2.5">
          <Globe2 className="h-4 w-4 text-[var(--accent-primary)] shrink-0" aria-hidden="true" />
          <div>
            <span className="font-bold text-[var(--text-primary)]">
              Kho dữ liệu công bố SEC EDGAR (Hoa Kỳ — USD)
            </span>
            <span className="text-[var(--text-secondary)]">
              {' '}
              · Doanh nghiệp niêm yết Hoa Kỳ phục vụ sàng lọc, kiểm thử kịch bản và đối chiếu chuẩn ngành, tách biệt hoàn toàn với Danh bạ Tổ chức (VND).
            </span>
          </div>
        </div>
        <span className="num text-[11px] font-bold px-2 py-0.5 rounded-[2px] bg-[var(--bg-surface)] text-[var(--accent-primary)] border border-[var(--accent-border)]">
          US GAAP · USD
        </span>
      </div>

      <ScreenerPage />
    </div>
  );
}
