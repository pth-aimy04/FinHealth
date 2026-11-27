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
import { PageHeader, Panel, PanelHeader } from '@/components/ui/Primitives';

export function MethodologyPage() {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
  });

  const reportedVersion = healthQuery.data?.active_model_version;
  const activeVersion =
    reportedVersion && reportedVersion.startsWith('v2')
      ? reportedVersion
      : 'v2.0.0-kaggle (Scale-Free Ensemble)';

  return (
    <div className="space-y-6 animate-view max-w-5xl">
      <PageHeader
        title="Phương pháp luận & Minh bạch Kiểm định"
        description="Tài liệu chuẩn hóa dành cho Hội đồng Quản trị, Phòng Thẩm định Tín dụng và Kiểm toán nội bộ về cơ sở dữ liệu, quy trình kiểm định ngoài mẫu thời gian và phạm vi áp dụng của FinHealth."
      />

      {/* Flush 3-Column Governance Highlights Strip */}
      <div className="surface-ruled grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-[var(--border-subtle)]">
        <div className="p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.04em] text-[var(--accent-primary)]">
            <Database className="h-4 w-4" aria-hidden="true" />
            <span>Dữ liệu Huấn luyện & Đối chiếu</span>
          </div>
          <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed m-0">
            Huấn luyện trên bộ dữ liệu lịch sử doanh nghiệp Hoa Kỳ giai đoạn 1999–2018 (78.682 quan
            sát doanh nghiệp–năm) kết hợp kho báo cáo SEC EDGAR để xây dựng chuẩn phân vị ngành.
          </p>
        </div>

        <div className="p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.04em] text-[var(--accent-primary)]">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            <span>Kiểm định Thời gian Nghiêm ngặt</span>
          </div>
          <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed m-0">
            Phân tách tuyệt đối theo trục thời gian (Train ≤ 2014 · Validation 2015–2016 · Test
            2017–2018) với 0% trùng lặp doanh nghiệp phá sản giữa tập huấn luyện và tập kiểm thử.
          </p>
        </div>

        <div className="p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.04em] text-[var(--accent-primary)]">
            <TrendingUp className="h-4 w-4" aria-hidden="true" />
            <span>Bất biến Đơn vị Tiền tệ</span>
          </div>
          <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed m-0">
            100% đặc trưng đầu vào là tỷ số tài chính không thứ nguyên (scale-free). Quy đổi giữa
            VND, Triệu VND, Tỷ VND và USD cho kết quả xác suất rủi ro đồng nhất tuyệt đối.
          </p>
        </div>
      </div>

      {/* 5 Pillars & Scoring Scale */}
      <Panel className="overflow-hidden">
        <PanelHeader
          title="1. Hệ thống 5 Trụ cột Sức khỏe & Thang điểm Thống nhất (0–100)"
          description={`Phiên bản mô hình đang vận hành: ${activeVersion}`}
        />
        <div className="p-5 space-y-5 text-[13px] text-[var(--text-secondary)] leading-relaxed">
          <p className="m-0">
            Mỗi doanh nghiệp chỉ có{' '}
            <strong className="text-[var(--text-primary)]">
              01 Điểm Sức khỏe Tài chính duy nhất (0–100)
            </strong>
            , được ánh xạ đơn điệu từ Xác suất Nguy cơ khủng hoảng 12 tháng đã hiệu chuẩn xác suất và
            phân thành 4 cấp độ chuẩn hóa:
          </p>

          <div className="overflow-x-auto border border-[var(--border-subtle)] rounded-[2px]">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Cấp độ sức khỏe</th>
                  <th className="text-right">Thang điểm (0–100)</th>
                  <th className="text-right">Nguy cơ khủng hoảng 12 tháng</th>
                  <th>Ý nghĩa quản trị</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="font-bold text-[var(--risk-low-fg)]">Vững mạnh</td>
                  <td className="text-right num font-semibold">80,0 – 100</td>
                  <td className="text-right num">&lt; 1,0%</td>
                  <td className="text-[var(--text-secondary)]">Nền tảng tài chính vững chắc, khả năng chống chịu tốt</td>
                </tr>
                <tr>
                  <td className="font-bold text-[var(--risk-stable-fg)]">Ổn định</td>
                  <td className="text-right num font-semibold">60,0 – 80,0</td>
                  <td className="text-right num">1,0% – 3,0%</td>
                  <td className="text-[var(--text-secondary)]">Hoạt động ổn định, rủi ro trong ngưỡng kiểm soát</td>
                </tr>
                <tr>
                  <td className="font-bold text-[var(--risk-medium-fg)]">Cần theo dõi sát</td>
                  <td className="text-right num font-semibold">35,0 – 60,0</td>
                  <td className="text-right num">3,0% – 8,0%</td>
                  <td className="text-[var(--text-secondary)]">Có dấu hiệu áp lực dòng tiền hoặc đòn bẩy nợ</td>
                </tr>
                <tr>
                  <td className="font-bold text-[var(--risk-critical-fg)]">Nguy cơ khủng hoảng cao</td>
                  <td className="text-right num font-semibold">0,0 – 35,0</td>
                  <td className="text-right num">&ge; 8,0%</td>
                  <td className="text-[var(--text-secondary)]">Cảnh báo sớm rủi ro mất khả năng thanh toán trong 12 tháng</td>
                </tr>
              </tbody>
            </table>
          </div>

          <ul className="space-y-2 list-none p-0 m-0">
            {[
              'Khả năng thanh toán ngắn hạn (20%): Thanh toán hiện hành, thanh toán nhanh, tiền mặt, vốn lưu động.',
              'Cơ cấu vốn & Áp lực nợ vay (25%): Tỷ lệ nợ, vốn chủ/tổng tài sản, nợ ngắn hạn, khả năng trả lãi vay, lợi nhuận giữ lại (áp mức phạt 0 điểm khi âm VCSH).',
              'Khả năng sinh lời (20%): Biên gộp, biên hoạt động, biên EBITDA, ROA, ROE.',
              'Hiệu quả luân chuyển vốn (15%): Vòng quay tổng tài sản, số ngày thu tiền bình quân (DSO), số ngày tồn kho (DIO).',
              'Sức mạnh dòng tiền thực (20%): Dòng tiền HĐKD / Tổng nợ, dòng tiền tự do / Tổng nợ, tỷ lệ chuyển hóa tiền mặt (QoE).',
            ].map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 text-[var(--accent-primary)] shrink-0 mt-0.5" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </Panel>

      {/* Altman & Financial Institution Scope */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel className="overflow-hidden">
          <PanelHeader
            title="2. Chỉ số Altman Z-Score Đủ 3 Biến thể"
            description="Tự động chọn công thức và ngưỡng vùng theo loại hình doanh nghiệp."
          />
          <div className="overflow-x-auto">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Biến thể</th>
                  <th>Đối tượng áp dụng</th>
                  <th className="text-right">Nguy hiểm / An toàn</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="num font-bold text-[var(--accent-primary)]">Z</td>
                  <td>Sản xuất niêm yết (vốn hóa thị trường)</td>
                  <td className="text-right num">&lt; 1,81 · &gt; 2,99</td>
                </tr>
                <tr>
                  <td className="num font-bold text-[var(--accent-primary)]">Z&apos;</td>
                  <td>Sản xuất chưa niêm yết (VCSH sổ sách)</td>
                  <td className="text-right num">&lt; 1,23 · &gt; 2,90</td>
                </tr>
                <tr>
                  <td className="num font-bold text-[var(--accent-primary)]">Z&apos;&apos;</td>
                  <td>Thương mại, Dịch vụ & Phi sản xuất</td>
                  <td className="text-right num">&lt; 1,10 · &gt; 2,60</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel className="overflow-hidden">
          <PanelHeader
            title="3. Phạm vi Loại trừ & Độ tin cậy 4 Lớp"
            description="Bảo vệ người dùng khỏi việc áp dụng sai phạm vi mô hình."
          />
          <div className="p-5 space-y-3 text-[13px] text-[var(--text-secondary)] leading-relaxed">
            <div className="flex items-start gap-2.5">
              <Building2 className="h-4 w-4 text-[var(--risk-high-fg)] shrink-0 mt-1" />
              <span>
                <strong className="text-[var(--text-primary)]">
                  Tự động chặn Ngân hàng, Bảo hiểm & Tổ chức tài chính:
                </strong>{' '}
                Cấu trúc bảng cân đối đặc thù của TCTC không tương thích với mô hình doanh nghiệp
                phi tài chính và Altman Z-Score.
              </span>
            </div>
            <p className="m-0">
              Mọi kết quả đều đi kèm chỉ báo{' '}
              <strong className="text-[var(--text-primary)]">Độ tin cậy 4 lớp</strong> dựa trên: (1)
              Tỷ lệ đầy đủ chỉ tiêu BCTC, (2) Kiểm tra giá trị ngoại lệ so với phân phối chuẩn, (3)
              Độ đồng thuận giữa các mô hình đánh giá, và (4) Trạng thái kiểm toán của báo cáo tài
              chính.
            </p>
          </div>
        </Panel>
      </div>

      {/* Mandatory Legal Disclaimer (Decree 88/2014/ND-CP) — Full Border Institutional Notice */}
      <section
        aria-label="Điều khoản miễn trừ trách nhiệm pháp lý"
        className="p-5 rounded-[3px] border border-[var(--risk-medium-border)] bg-[var(--risk-medium-bg)]/55 space-y-2"
      >
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.05em] text-[var(--risk-medium-fg)]">
          <Scale className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>Khung Pháp lý & Miễn trừ Trách nhiệm (Nghị định 88/2014/NĐ-CP)</span>
        </div>
        <p className="text-[13px] text-[var(--text-primary)] leading-relaxed m-0">
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
