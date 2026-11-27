> 26/11/2026: Tài liệu lịch sử. React hiện là giao diện chính; Tabler và preview đã được lưu tại `frontend/legacy`, ngoài static root. Xem `docs/frontend-migration.md` và README để chạy bản hiện tại.

# FinHealth — bản xem trước Tabler

> Cập nhật 24/11/2026: Bản thiết kế đã được đưa lên trang chính `/`. Bản xem
> trước vẫn được giữ tại đường dẫn cũ. Bản sao giao diện trước khi chuyển nằm tại
> `D:/DATN/.venv/ui-baselines/before-tablerview-20261124_013357/frontend/`;
> đối chiếu tệp `manifest.json` cùng thư mục trước khi khôi phục. Bản sao này
> chỉ gồm frontend, không phải bản sao lưu dữ liệu hoặc database. Các ghi chú bên
> dưới mô tả trạng thái lúc triển khai bản xem trước.

## Phạm vi đợt đầu

Bản xem trước độc lập tại `http://127.0.0.1:8000/static/preview/index.html`.
Trang chính `/` vẫn sử dụng frontend hiện tại. Chưa chuyển mặc định sang Tabler.

Ba màn hình cần duyệt: `#screener`, `#company`, `#admin` (cần tài khoản quản trị).
Các màn hình so sánh, giải thích, dự báo thủ công, mô hình và kho báo cáo cũng được
giữ trong bản xem trước để kiểm tra khả năng tương thích, chưa coi là thiết kế cuối.

Tabler Core 1.7.5 được lưu cục bộ trong `frontend/vendor/tabler/1.7.5` cùng giấy phép
MIT và nguồn gốc gói. Đã kiểm tra SHA-512 của gói tải từ npm. Không tải font, CSS hay
JavaScript từ CDN khi mở ứng dụng. Chỉ nạp CSS Tabler; chưa nạp JavaScript Tabler
vì điều hướng và dialog đang dùng bộ điều khiển hiện có. Không nạp Bootstrap lần hai.

## Chức năng được giữ

| Nhóm | Cách giữ trong bản xem trước |
| --- | --- |
| Tra cứu công khai | Không tự mở đăng nhập khi vào ứng dụng |
| Sàng lọc | Giữ ID điều khiển, tìm kiếm, lọc ngành/rủi ro/nhóm/năm và các tỷ số, sắp xếp, CSV |
| Phân tích công ty | Giữ số liệu, nguồn báo cáo, dự báo, tín dụng, mô phỏng và báo cáo in |
| So sánh, SHAP, dự báo thủ công, mô hình | Giữ panel và bộ điều khiển cũ |
| Kho báo cáo | Dùng nguyên mô-đun báo cáo, API và truy xuất nguồn |
| Tài khoản và OTP | Giữ cookie phiên, CSRF, đăng nhập, đăng ký, OTP và không gian cá nhân |
| Quản trị | Giữ yêu cầu cập nhật, lịch sử, chi tiết tác vụ, chạy lại, tài khoản, huấn luyện và nhật ký; chuyển nội dung sang trang riêng |

Các mô-đun `api.js`, `charts.js`, `csv.js`, `reports.js`, `vi.js` giống từng byte
với frontend chính. Không thay đổi backend, migration, SQL Server, mô hình hay dữ
liệu tài chính. Bản xem trước dùng **cùng API và database thật** với trang chính;
các nút quản trị vẫn thực hiện tác vụ thật khi người có quyền sử dụng.

Khi hết phiên hoặc mất quyền quản trị, nội dung quản trị đã tải được xóa khỏi DOM.
Phân quyền vẫn được kiểm tra tại API; ẩn nút ở frontend chỉ phục vụ trải nghiệm.

## Kiểm tra

Các kiểm tra ASGI offline trong `tests/integration/test_tabler_preview.py` xác nhận
giữ các ID cũ, không trùng ID, tham chiếu nhãn hợp lệ, tài nguyên nội bộ được phục
vụ đúng, CSP, giới hạn đường dẫn static và trang chính độc lập.

Kiểm tra DOM bổ sung (không phải trình duyệt có render):

```powershell
npm install --prefix .venv/ui-tools --cache D:/DATN/.venv/npm-cache --no-save --no-audit --no-fund jsdom@26.1.0 esbuild@0.25.12 @esbuild/win32-x64@0.25.12
node tests/frontend/tabler_preview.cjs
```

Script cần API cục bộ đang chạy, dùng GET để đọc dữ liệu tài chính thật. Ranh giới
xác thực/quản trị được thay bằng fixture; yêu cầu ghi thật bị chặn. Script kiểm tra
khởi tạo, chuyển màn hình, tìm kiếm/đặt lại, menu thu gọn, đăng nhập theo hành động,
chuyển sang nhập OTP, quản trị toàn trang, quay lại sau dialog và hết phiên.
Không dùng kết quả DOM để khẳng định layout hoặc đăng nhập quản trị thật đã được duyệt.

Hai lệnh bắt buộc từ thư mục gốc:

```powershell
ruff check .
pytest -v
```

Output nguyên văn được lưu tại `audit-reports/tabler-preview-ruff.txt` và
`audit-reports/tabler-preview-pytest.txt`; kết quả DOM tại
`audit-reports/tabler-preview-dom.txt`.

Lần chạy đầy đủ đầu tiên gặp `ArrayMemoryError` khi Matplotlib xuất PNG 300 DPI
(cần cấp phát thêm khoảng 39 MiB). Kiểm tra riêng cùng bài đó đã đạt mà không sửa
mã tài chính hay hạ độ phân giải. Output lần đầu được giữ tại
`audit-reports/tabler-preview-pytest-first-run.txt`, output chạy lại riêng tại
`audit-reports/tabler-preview-plot-recheck.txt`. Lần chạy đầy đủ sau đặt
`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` bằng `1` để giới hạn
tài nguyên tính toán; không bỏ qua hoặc sửa điều kiện kiểm tra.

Kết quả cuối: `ruff check .` — `All checks passed!`; `pytest -v` —
`200 passed, 33 skipped, 1 warning in 167.31s (0:02:47)`.
Các kiểm tra cần snapshot SQLite cục bộ bị bỏ qua; kiểm tra SQL Server thực tế
đã chạy và đạt. Cảnh báo là thông báo deprecation của Starlette/httpx.
Kiểm tra DOM khách và quản trị đều đạt ở lần chạy riêng cuối cùng.
Một lần chạy DOM đồng thời với bộ kiểm thử ML gặp timeout tải phân tích công ty;
log được giữ tại `audit-reports/tabler-preview-dom-concurrent-run.txt`.
Nên chạy hai nhóm tuần tự trên máy hiện tại.

Kiểm tra trực quan tự động chưa thực hiện được: trình duyệt tích hợp không khả dụng,
Computer Use dừng vì không xác định chắc chắn URL hiện tại của Edge. Cần duyệt trên
desktop và màn hình nhỏ: độ rộng bảng, nội dung dài, biểu đồ, dialog và khu quản trị
với phiên đăng nhập thực tế. Không tuyên bố không còn lỗi chỉ từ kiểm tra tự động.

## Khôi phục và bước chuyển tiếp

Bản sao 12 tệp frontend trước thay đổi và SHA-256 nằm tại:
`D:/DATN/.venv/ui-baselines/20261123_203953/`.
Đối chiếu manifest xác nhận các tệp gốc không thay đổi trong đợt này.
Đây là bản sao cục bộ; không thay thế bản sao lưu dữ liệu hay lịch sử Git.

Nếu bản xem trước có lỗi, dùng liên kết **Về giao diện hiện tại** hoặc mở `/`;
không cần sửa database hay khôi phục dữ liệu. Chưa có thay đổi trang chính cần rollback.
Repository hiện chưa có commit HEAD nên không dùng `git reset` để khôi phục.

Sau khi duyệt ba màn hình đại diện: hoàn thiện các màn hình còn lại, kiểm thử trực
quan và luồng nghiệp vụ thực tế, chụp bản sao mới rồi mới chuyển trang mặc định.
Giữ bản cũ để quay lại trong đợt chuyển chính thức và chạy lại các kiểm tra sau khi chuyển.
