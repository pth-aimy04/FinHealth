import { useQuery } from '@tanstack/react-query';
import {
  Building2,
  CheckCircle2,
  Database,
  Scale,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Panel, PanelHeader } from '@/components/ui/Primitives';

export function MethodologyPage() {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
  });

  const activeVersion = healthQuery.data?.active_model_version ?? 'v2.0.0-kaggle';

  return (
    <div className="space-y-6 animate-view max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-[-0.025em] text-[var(--text-primary)]">
          Phương pháp luận & Minh bạch Kiểm định
        </h1>
        <p className="mt-1 text-xs sm:text-sm text-[var(--text-secondary)]">
          Tài liệu chuẩn hóa dành cho Hội đồng Quản trị, Phòng Thẩm định Tín dụng và Kiểm toán nội
          bộ về cơ sở dữ liệu, quy trình kiểm định ngoài mẫu thời gian và phạm vi áp dụng của
          FinHealth.
        </p>
      </div>

      {/* Key Governance Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Panel className="p-4 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--accent-primary)]">
            <Database className="h-4 w-4" aria-hidden="true" />
            <span>Dữ liệu Huấn luyện & Đối chiếu</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Huấn luyện trên bộ dữ liệu lịch sử doanh nghiệp Hoa Kỳ giai đoạn 1999–2018 (78.682 quan
            sát doanh nghiệp–năm) kết hợp kho báo cáo SEC EDGAR để xây dựng chuẩn phân vị ngành.
          </p>
        </Panel>

        <Panel className="p-4 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--accent-primary)]">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            <span>Kiểm định Thời gian Nghiêm ngặt</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Phân tách tuyệt đối theo trục thời gian (Train ≤ 2014 · Validation 2015–2016 · Test
            2017–2018) với 0% trùng lặp doanh nghiệp phá sản giữa tập huấn luyện và tập kiểm thử.
          </p>
        </Panel>

        <Panel className="p-4 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--accent-primary)]">
            <TrendingUp className="h-4 w-4" aria-hidden="true" />
            <span>Bất biến Đơn vị Tiền tệ</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            100% đặc trưng đầu vào là tỷ số tài chính không thứ nguyên (scale-free). Quy đổi giữa
            VND, Triệu VND, Tỷ VND và USD cho kết quả xác suất rủi ro đồng nhất tuyệt đối.
          </p>
        </Panel>
      </div>

      {/* 5 Pillars & Scoring Scale */}
      <Panel>
        <PanelHeader
          title="1. Hệ thống 5 Trụ cột Sức khỏe & Thang điểm Thống nhất (0–100)"
          description={`Phiên bản mô hình đang vận hành: ${activeVersion}`}
        />
        <div className="p-5 space-y-4 text-xs text-[var(--text-secondary)] leading-relaxed">
          <p>
            Mỗi doanh nghiệp chỉ có <strong className="text-[var(--text-primary)]">01 Điểm Sức khỏe Tài chính duy nhất (0–100)</strong>,
            được ánh xạ đơn điệu từ Xác suất Nguy cơ khủng hoảng 12 tháng đã hiệu chuẩn xác suất và
            phân thành 4 cấp độ trực quan:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="p-3 rounded-[6px] border border-[var(--border-subtle)] bg-[var(--risk-low-bg)]/45">
              <div className="font-semibold text-[var(--risk-low-fg)]">Vững mạnh (85–100)</div>
              <div className="mt-1 text-[11px]">Nguy cơ 12 tháng &lt; 1,0%</div>
            </div>
            <div className="p-3 rounded-[6px] border border-[var(--border-subtle)] bg-[var(--accent-soft)]/50">
              <div className="font-semibold text-[#1D4ED8]">Ổn định (65–85)</div>
              <div className="mt-1 text-[11px]">Nguy cơ 12 tháng 1,0% – 3,0%</div>
            </div>
            <div className="p-3 rounded-[6px] border border-[var(--border-subtle)] bg-[var(--risk-medium-bg)]/50">
              <div className="font-semibold text-[var(--risk-medium-fg)]">
                Cần theo dõi sát (40–65)
              </div>
              <div className="mt-1 text-[11px]">Nguy cơ 12 tháng 3,0% – 8,0%</div>
            </div>
            <div className="p-3 rounded-[6px] border border-[var(--border-subtle)] bg-[var(--risk-critical-bg)]/50">
              <div className="font-semibold text-[var(--risk-critical-fg)]">
                Nguy cơ khủng hoảng cao (0–40)
              </div>
              <div className="mt-1 text-[11px]">Nguy cơ 12 tháng &gt; 8,0%</div>
            </div>
          </div>

          <ul className="space-y-1.5 pt-1">
            {[
              'Khả năng thanh toán ngắn hạn (20%): Thanh toán hiện hành, thanh toán nhanh, tiền mặt, vốn lưu động.',
              'Cơ cấu vốn & Áp lực nợ vay (25%): Tỷ lệ nợ, vốn chủ/tổng tài sản, nợ ngắn hạn, khả năng trả lãi vay, lợi nhuận giữ lại (áp mức phạt 0 điểm khi âm VCSH).',
              'Khả năng sinh lời (25%): Biên gộp, biên hoạt động, biên EBITDA, ROA, ROE.',
              'Hiệu quả luân chuyển vốn (15%): Vòng quay tổng tài sản, số ngày thu tiền bình quân (DSO), số ngày tồn kho (DIO).',
              'Sức mạnh dòng tiền thực (15%): Dòng tiền HĐKD / Tổng nợ, dòng tiền tự do / Tổng nợ, tỷ lệ chuyển hóa tiền mặt (QoE).',
            ].map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-[var(--accent-primary)] shrink-0 mt-0.5" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </Panel>

      {/* Altman & Financial Institution Scope */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel>
          <PanelHeader
            title="2. Chỉ số Altman Z-Score Đủ 3 Biến thể"
            description="Tự động chọn công thức và ngưỡng vùng theo loại hình doanh nghiệp."
          />
          <div className="p-5 space-y-2.5 text-xs text-[var(--text-secondary)]">
            <div>
              <strong className="text-[var(--text-primary)]">Altman Z (Sản xuất niêm yết):</strong>{' '}
              Sử dụng vốn hóa thị trường; ngưỡng Nguy hiểm &lt; 1,81 · Vùng xám 1,81–2,99 · An toàn
              &gt; 2,99.
            </div>
            <div>
              <strong className="text-[var(--text-primary)]">
                Altman Z&apos; (Sản xuất chưa niêm yết):
              </strong>{' '}
              Sử dụng vốn chủ sở hữu sổ sách; ngưỡng Nguy hiểm &lt; 1,23 · Vùng xám 1,23–2,90 · An
              toàn &gt; 2,90.
            </div>
            <div>
              <strong className="text-[var(--text-primary)]">
                Altman Z&apos;&apos; (Thương mại, Dịch vụ & Phi sản xuất):
              </strong>{' '}
              Loại bỏ hệ số vòng quay tài sản; ngưỡng Nguy hiểm &lt; 1,10 · Vùng xám 1,10–2,60 · An
              toàn &gt; 2,60.
            </div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="3. Phạm vi Loại trừ & Độ tin cậy 4 Lớp"
            description="Bảo vệ người dùng khỏi việc áp dụng sai phạm vi mô hình."
          />
          <div className="p-5 space-y-2.5 text-xs text-[var(--text-secondary)]">
            <div className="flex items-start gap-2">
              <Building2 className="h-4 w-4 text-[var(--risk-high-fg)] shrink-0 mt-0.5" />
              <span>
                <strong className="text-[var(--text-primary)]">
                  Tự động chặn Ngân hàng, Bảo hiểm & Tổ chức tài chính:
                </strong>{' '}
                Cấu trúc bảng cân đối đặc thù của TCTC không tương thích với mô hình doanh nghiệp
                phi tài chính và Altman Z-Score.
              </span>
            </div>
            <p>
              Mọi kết quả đều đi kèm chỉ báo <strong className="text-[var(--text-primary)]">Độ tin cậy 4 lớp</strong>{' '}
              dựa trên: (1) Tỷ lệ đầy đủ chỉ tiêu BCTC, (2) Kiểm tra giá trị ngoại lệ so với phân
              phối chuẩn, (3) Độ đồng thuận giữa các mô hình đánh giá, và (4) Trạng thái kiểm toán
              của báo cáo tài chính.
            </p>
          </div>
        </Panel>
      </div>

      {/* Mandatory Legal Disclaimer (Decree 88/2014/ND-CP) */}
      <section
        aria-label="Điều khoản miễn trừ trách nhiệm pháp lý"
        className="surface p-5 border-l-4 border-l-[var(--risk-medium-fg)] space-y-2"
      >
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-[var(--text-primary)]">
          <Scale className="h-4 w-4 text-[var(--risk-medium-fg)]" aria-hidden="true" />
          <span>Khung Pháp lý & Miễn trừ Trách nhiệm (Nghị định 88/2014/NĐ-CP)</span>
        </div>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          Kết quả đánh giá sức khỏe tài chính và xác suất rủi ro 12 tháng do FinHealth cung cấp là
          công cụ phân tích định lượng nội bộ dựa trên mô hình thống kê từ dữ liệu tài chính lịch
          sử. Dịch vụ này <strong>không phải là hoạt động xếp hạng tín nhiệm</strong> theo quy định
          tại Nghị định 88/2014/NĐ-CP của Chính phủ và không thay thế quyết định phê duyệt tín dụng,
          quyết định đầu tư hay ý kiến kiểm toán độc lập.
        </p>
      </section>
    </div>
  );
}
