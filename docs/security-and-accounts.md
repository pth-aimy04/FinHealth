# Tài khoản, phân quyền và quản trị FinHealth

## Khởi động

Từ `D:\DATN`, kích hoạt `.venv`, cài `pip install -e ".[dev,sqlserver]"`,
chạy `alembic upgrade head`, rồi khởi động lại API. Migration 0005 bổ sung tài khoản,
phiên, dữ liệu cá nhân và lịch sử quản trị; không thay thế dữ liệu báo cáo tài chính.
Migration 0006 bổ sung bảng `email_verification_codes` cho OTP đăng ký.
Sao lưu database trước khi migration trên một bản đang sử dụng.

Trang đầu vẫn là sàng lọc công khai. Theo dõi, lưu dữ liệu, in/xuất kết quả, dự báo
thủ công và phân tích CSV hàng loạt yêu cầu đăng nhập. Đăng nhập xong sẽ tiếp tục thao tác;
đóng hộp thoại giữ nguyên dữ liệu đang nhập. Không có tài khoản quản trị mặc định.

Tạo quản trị viên đầu tiên trong terminal cục bộ (mật khẩu nhập ẩn, tối thiểu 12 ký tự):

```powershell
python -m finhealth.core.account_cli create-admin --email dia-chi-cua-ban@example.com
```

Lệnh này là xác nhận trực tiếp của người vận hành và tạo admin đã xác thực, không
cần SMTP. Để khôi phục admin khi mất mật khẩu hoặc dịch vụ email chưa sẵn sàng:

```powershell
python -m finhealth.core.account_cli reset-admin --email dia-chi-cua-ban@example.com
```

Không dùng địa chỉ ví dụ để gửi thư thật. API đăng ký luôn tạo `user`, không nhận `role`.
Không thể khóa tài khoản quản trị qua giao diện; khôi phục quản trị nằm ngoài API công khai.

## Quản trị dữ liệu

Màn hình quản trị dành cho tài khoản `admin`. Phần tình trạng vận hành hiển thị số tác
vụ chờ, đang chạy, thất bại, trạng thái bộ xử lý, cấu hình email và lần cập nhật thành
công gần nhất. Nút làm mới tải lại thông tin hiện tại.

Mục **Yêu cầu cập nhật** nhận tối đa 10 ticker hoặc CIK, phân cách bằng dấu phẩy; API
đưa mỗi yêu cầu vào hàng đợi và tránh tạo tác vụ trùng đang chờ hoặc chạy. Bộ xử lý
phải bật để tiếp nhận tác vụ. **Lịch sử cập nhật** hiển thị từng yêu cầu; nút **Xem**
mở trạng thái và các sự kiện được ghi lại ngay dưới dòng đó. Một số bản ghi cũ có thể
không có sự kiện chi tiết; màn hình thông báo rõ và không tự tạo lịch sử giả. Nút
**Chạy lại** chỉ áp dụng cho tác vụ thất bại, tạo một yêu cầu mới có liên kết về
yêu cầu cũ. Cột **Người yêu cầu** hiển thị tên và email hiện tại của tài khoản gắn với
yêu cầu; nếu tên hoặc email tài khoản thay đổi thì lịch sử hiển thị thông tin mới.
Bản ghi không có tài khoản được ghi là không có thông tin. API lịch sử này chỉ dành
cho quản trị viên. Ba danh sách lịch sử, tài khoản và nhật ký có phân trang độc lập, mỗi danh
sách tối đa 50 mục một trang. Nếu một danh sách không tải được, giao diện hiển thị lỗi
ngay tại danh sách đó.

Các phần còn lại gồm quản lý tài khoản (xem, khóa, mở khóa người dùng thông thường)
và nhật ký quản trị. Khóa tài khoản thu hồi các phiên của tài khoản đó. Chức năng
huấn luyện và công bố đã được bỏ khỏi giao diện quản trị; API huấn luyện vẫn tồn tại
và vẫn yêu cầu quyền quản trị. Không chạy cập nhật hoặc khóa tài khoản chỉ để thử giao
diện trên dữ liệu thật.

## Email

Cấu hình trong `.env`, không đưa mật khẩu ứng dụng vào chat, ảnh hoặc Git:

```dotenv
PUBLIC_BASE_URL=http://localhost:8000
SESSION_HOURS=8
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_FROM_NAME=FinHealth
MAIL_TIMEOUT_SECONDS=15
```

Dùng Gmail riêng cho dự án, xác minh hai bước và App Password mới chưa bị lộ.
Khi triển khai, PUBLIC_BASE_URL phải là origin HTTPS của ứng dụng; staging/production
từ chối cấu hình HTTP. Dùng cùng origin cho frontend và API, reverse proxy chuyển
đúng scheme HTTPS và chỉ tin forwarded headers từ proxy được chỉ định.

SMTP dùng STARTTLS và xác minh chứng chỉ. Chưa cấu hình hoặc gửi thất bại trả 503;
không có chế độ in token ra log hoặc giả lập gửi thư. Kiểm thử chỉ thay transport SMTP.
Đăng ký dùng OTP 6 chữ số: đọc email trên điện thoại rồi nhập trên máy tính, không cần
truy cập localhost trên điện thoại. Đăng ký thành công chuyển sang hộp thoại OTP;
mật khẩu vừa chọn chỉ giữ trong bộ nhớ trong lúc xác thực, không lưu vào browser storage.
Mỗi mã có hạn 10 phút, tối đa 5 lần nhập sai và chỉ dùng một lần; mã được băm Argon2id,
gắn với email và challenge ngẫu nhiên của trình duyệt. Gửi lại thay thế mã cũ, chịu giới
hạn gửi theo email/IP và cửa sổ 60 giây. Nếu đóng/tải lại trang, dùng Gửi lại xác thực
để nhận mã mới và chọn mật khẩu trong màn hình OTP. Không cần mở liên kết từ email.

Tất cả yêu cầu xác thực qua email đều dùng OTP, không gửi URL hoặc yêu cầu mở
localhost từ điện thoại: đăng ký, khôi phục mật khẩu, đổi mật khẩu và đổi email.
Mỗi mã gắn với đúng mục đích, người dùng, địa chỉ nhận, challenge của trình duyệt và
phiên bản mật khẩu. Mã có hạn 10 phút, tối đa 5 lần nhập sai, dùng một lần; gửi lại
thay thế mã cũ của cùng mục đích. Mã được băm Argon2id; challenge được băm SHA-256.
Migration 0007 thêm `account_action_codes` và vô hiệu hóa các liên kết cũ.

Đổi mật khẩu cần đăng nhập, mật khẩu hiện tại và OTP gửi tới email hiện tại. Đổi
email cần đăng nhập, mật khẩu hiện tại và OTP gửi tới địa chỉ mới. Chỉ sau khi OTP
đúng mới cập nhật; sau đó thu hồi phiên và mọi mã còn lại. Quên mật khẩu cho nhập
email, nhận OTP, nhập mã và mật khẩu mới trên máy tính, không tự đăng nhập sau đó.
Thông báo hoàn tất chỉ cung cấp thông tin, không chứa mật khẩu, OTP mới hoặc URL.
Lỗi SMTP trước commit giữ nguyên mật khẩu/email; nếu database lỗi sau gửi thông báo,
email có thể đã tới nhưng thay đổi chưa commit. Không ghi mã vào log.

Không có mật khẩu quản trị mặc định. Khi sửa địa chỉ quản trị bằng thao tác nội bộ,
địa chỉ mới phải xác thực OTP trước khi đăng nhập; dùng Gửi lại xác thực, nhập email,
OTP và mật khẩu muốn dùng. Quyền admin giữ nguyên và không cho client tự chọn role.

## Quyền và dữ liệu cá nhân

Khách có thể tra cứu và xem kết quả phân tích công khai. API dự báo thủ công và hàng loạt
yêu cầu phiên đã xác thực và CSRF. Các nút in/xuất được kiểm tra phiên trong giao diện;
vì dữ liệu nguồn công khai, quy định này không ngăn tải hoặc sao chép dữ liệu qua cách khác.
Người dùng đã xác thực lưu tối đa 200 mục
mỗi loại: doanh nghiệp theo dõi, bộ lọc và kết quả dự báo. Chỉ lưu khi chủ động bấm lưu.
Kết quả lưu được tính lại trên server với phiên bản mô hình đã chọn, không tin output
do client gửi. Chỉ chủ sở hữu được xem/xóa; admin không có API đọc dữ liệu riêng này.

Cookie phiên HttpOnly, SameSite=Strict, Secure với HTTPS; token phiên và CSRF lưu dạng
băm. Các thao tác ghi yêu cầu CSRF và kiểm tra Origin. Phiên mặc định 8 giờ, có kiểm
tra trạng thái hoạt động, xác thực email và phiên bản mật khẩu trên mỗi yêu cầu.
Không còn ADMIN_TOKEN hoặc bypass xác thực ở development/test.

Giới hạn dùng counter SQL chung giữa các API process, không tin X-Forwarded-For từ
client. Nếu triển khai sau proxy, cấu hình trusted proxy để direct peer phản ánh IP
đã được xác minh; nếu không, người dùng có thể dùng chung quota của proxy.
Quota mặc định theo cửa sổ 10 phút: đăng nhập 20/IP và 10/email; email 3/địa chỉ;
đăng ký/quên mật khẩu 5/IP; dự báo 30/IP; lưu dự báo 20/IP; cập nhật 30/IP;
huấn luyện 5/IP. Khóa tài khoản thu hồi phiên ngay. Giới hạn JSON 2 MB,
batch tối đa 200 doanh nghiệp; thông tin xác thực không được log.

## Cập nhật SQL Server

Đăng nhập admin, mở Tài khoản → Quản trị hệ thống. Trang có kết nối database,
trạng thái worker/SMTP, tác vụ theo trang, chi tiết sự kiện, chạy lại tác vụ lỗi,
khóa/mở user, huấn luyện và nhật ký. Bấm Làm mới để lấy trạng thái mới.
Có thể gửi tối đa 10 ticker/CIK trong một lần thao tác giao diện.

`ingestion_runs` lưu actor, thời gian, bước và liên kết lần chạy lại. Unique index
có điều kiện `active_key IS NOT NULL` chống tác vụ trùng giữa tiến trình.
`ingestion_run_events` ghi bước thực sự đã xảy ra, không dựng phần trăm giả.
Tác vụ cũ không có actor giữ NULL. Các trường chưa đo được (số dòng cập nhật hoặc
phần trăm chi tiết) không được suy đoán. Ngày báo cáo vẫn xem trong kho báo cáo.
Ghi số liệu qua pipeline/transaction, giữ nguồn và phiên bản sửa đổi; không có SQL tùy ý.

Chỉ chạy một API process với INGESTION_WORKER_ENABLED=true trong triển khai ban đầu;
không chạy các CLI ingestion hoặc worker khác cùng SEC identity. Rate limiter SEC hiện
chia sẻ trong một event loop, không phải limiter phân tán. Muốn mở rộng nhiều máy
phải triển khai điều phối chung trước, bảo đảm tổng không vượt 10 requests/giây.
API analyze tương thích cũ vẫn yêu cầu admin và từ chối khi queue được bật.

Huấn luyện hiện là tác vụ đồng bộ: ghi yêu cầu audit trước, service huấn luyện rồi công
bố như luồng hiện có; thành công được ghi thêm audit. Nếu tiến trình dừng, audit có
thể còn `requested`; không suy diễn thành công. Không gửi lại khi tác vụ đang chạy.

## Triển khai và kiểm tra

SQL Server chỉ mở trong mạng nội bộ/firewall được phép. Cấp tài khoản dịch vụ quyền
cần thiết trên bảng ứng dụng, không sysadmin; tài khoản migration và backup riêng.
PUBLIC API vẫn cần ghi bảng rate limit, nên không cấp read-only toàn database.
Dùng chứng chỉ SQL đáng tin cậy (`TrustServerCertificate=no`) khi triển khai.
Định kỳ backup, kiểm tra restore trên bản riêng; tài khoản ứng dụng không được xóa audit.
Không tự động sửa quyền SQL Server/Windows Authentication hiện tại của máy phát triển.

Chạy `ruff check .` và `pytest -v`. Test offline dùng SQLite tạm, không được mặc định
ghi vào database phát triển. SQL Server smoke test chỉ chạy khi bật tường minh:

```powershell
$env:FINHEALTH_SQLSERVER_TEST_ENABLED='1'
pytest tests/integration/test_sqlserver_accounts.py -v
Remove-Item Env:FINHEALTH_SQLSERVER_TEST_ENABLED
```

Yêu cầu DATABASE_URL trỏ SQL Server đã migration 0007. Mọi dữ liệu test nằm trong
transaction ngoài được rollback, không gửi email hoặc gọi SEC.
Các test audit cũ cần snapshot SQLite/artifact cục bộ sẽ skip nếu thiếu, không đại diện
cho việc đã kiểm tra snapshot bị thiếu. Gửi email thật chỉ nghiệm thu sau khi cấu hình
hộp thư và kiểm tra thư xác thực, khôi phục, thông báo trong hộp thư thật.
