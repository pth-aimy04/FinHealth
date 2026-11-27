import { Globe } from 'lucide-react';
import { ScreenerPage } from './ScreenerPage';

export function UsMarketPage() {
  return (
    <div className="space-y-4 animate-view">
      <div className="surface px-4 py-3 flex flex-wrap items-center justify-between gap-2 border-l-4 border-l-[var(--accent-primary)]">
        <div className="flex items-center gap-2.5">
          <Globe className="h-4 w-4 text-[var(--accent-primary)] shrink-0" aria-hidden="true" />
          <div className="text-xs">
            <span className="font-semibold text-[var(--text-primary)]">
              Dữ liệu công bố SEC EDGAR (Hoa Kỳ — USD)
            </span>
            <span className="text-[var(--text-secondary)]">
              {' '}
              · Kho doanh nghiệp niêm yết Hoa Kỳ phục vụ sàng lọc, kiểm thử kịch bản và đối chiếu
              chuẩn ngành, tách biệt hoàn toàn với Danh bạ Doanh nghiệp nội bộ (VND).
            </span>
          </div>
        </div>
      </div>

      <ScreenerPage />
    </div>
  );
}
