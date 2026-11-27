# ĐẶC TẢ DANH SÁCH CHỨC NĂNG SẢN PHẨM (PRODUCTION / GO-LIVE)

## 1. Thông tin Tổng quan Dự án

* **Tên đề tài / Sản phẩm:** Ứng dụng Machine Learning trong đánh giá sức khỏe tài chính và dự báo nguy cơ phá sản doanh nghiệp.
* **Bài toán cốt lõi:** Đánh giá sức khỏe tài chính & Dự báo kiệt quệ tài chính / phá sản doanh nghiệp (*Financial Distress / Bankruptcy Prediction*).
* **Phương pháp & Mô hình xử lý ngầm (Backend Engine):** Altman Z-Score ($Z, Z', Z''$), Logistic Regression, Random Forest (RF), XGBoost, LightGBM.
* **Đối tượng người dùng cuối (End-Users):** Chủ doanh nghiệp, Giám đốc tài chính (CFO), Kế toán trưởng, Chuyên viên phân tích tín dụng, Nhà đầu tư, Bộ phận quản trị rủi ro đối tác.
* **Triết lý thiết kế sản phẩm Go-Live:** **Ẩn toàn bộ độ phức tạp kỹ thuật AI/ML xuống tầng xử lý ngầm** và giao tiếp 100% bằng ngôn ngữ nghiệp vụ kế toán – tài chính trực quan, dễ hiểu, phục vụ ra quyết định ngay lập tức.

---

## 2. Nguyên tắc Chuyển đổi: Từ Kỹ thuật AI sang Giao diện Người dùng (End-User UI)

| Thành phần Kỹ thuật (Chạy ngầm ở Backend) | Tuyệt đối KHÔNG đưa lên Giao diện | Cách hiển thị Thân thiện trên Giao diện Người dùng |
| :--- | :--- | :--- |
| **4 mô hình Machine Learning** *(Logistic Regression, RF, XGBoost, LightGBM)* | Menu chọn thuật toán, bảng 4 con số xác suất rời rạc gây bối rối | Hợp nhất thành **1 Điểm Sức Khỏe Tài Chính (thang 0–100)** và **1 Tỷ lệ Nguy cơ Khủng hoảng (%)**, đi kèm nhãn **Độ tin cậy đánh giá** *(Cao / Khá / Cần lưu ý)* dựa trên mức độ đồng thuận giữa các mô hình. |
| **Mô hình Altman Z-Score** *($Z, Z', Z''$)* | Bắt người dùng tự chọn công thức toán học | Người dùng chỉ khai báo *Ngành nghề* và *Trạng thái niêm yết* khi tạo hồ sơ công ty; hệ thống tự động tính và hiển thị thẻ **Chỉ số Z-Score chuẩn quốc tế** *(An toàn / Vùng xám / Nguy hiểm)*. |
| **Giải thích mô hình AI** *(Local SHAP)* | Biểu đồ kỹ thuật chứa từ khóa `SHAP value`, tên biến lập trình (`roa_lag1`, `d_to_e`) | Bảng phân tích **"Điểm Tựa & Điểm Nghẽn Tài Chính"** gồm 2 cột Xanh – Đỏ trình bày bằng ngôn ngữ tài chính dễ đọc. |
| **Tinh chỉnh ngưỡng phân loại** *(Decision Threshold)* | Thanh trượt số thập phân từ $0.10$ đến $0.90$, ma trận nhầm lẫn (*Confusion Matrix*) | Chế độ chọn **Góc nhìn thẩm định**: *Thận trọng (Ưu tiên bảo toàn vốn)* – *Tiêu chuẩn* – *Linh hoạt*. |
| **Tiền xử lý dữ liệu & Ngoại lai** *(Imputation, Winsorization)* | Thông báo lỗi kiểu dữ liệu (`Null`, `NaN`, `Float`), cấu hình tham số | **Trợ lý kiểm tra cân đối kế toán** chỉ rõ khoản mục đang bị lệch số liệu trên Báo cáo tài chính để người dùng kiểm tra lại. |
| **Huấn luyện & Đánh giá mô hình** *(ROC-AUC, PR-AUC, SMOTE, Retrain)* | Đưa biểu đồ ROC, nút bấm Train Model lên ứng dụng khách hàng | **Tách biệt hoàn toàn khỏi giao diện người dùng cuối**, chỉ vận hành nội bộ ở môi trường kỹ thuật của đội ngũ phát triển trước khi phát hành phiên bản mới. |

---

## 3. Tổng quan Ma trận Ưu tiên Chức năng (MoSCoW)

| Phân nhóm | Số lượng | Mục tiêu Sản phẩm | Phạm vi Triển khai |
| :--- | :---: | :--- | :--- |
| **MUST-HAVE** | 12 | Khung sản phẩm hoàn chỉnh từ đăng nhập, nhập BCTC chuẩn Việt Nam đến chấm điểm sức khỏe, giải thích nguyên nhân và xuất PDF | Bắt buộc hoàn thành 100% khi Go-Live |
| **SHOULD-HAVE** | 06 | Bổ sung ngữ cảnh trung bình ngành, cảnh báo xu hướng ngầm đa kỳ, chấm hàng loạt và theo dõi danh mục | Nên có để tối ưu trải nghiệm thực tế |
| **COULD-HAVE** | 05 | Công cụ giả lập kịch bản kinh doanh, cảnh báo chất lượng số liệu kế toán và so sánh trực diện các đối tác | Mở rộng gia tăng giá trị tư vấn |
| **WOULD-HAVE / INNOVATION** | 04 | Gợi ý lộ trình thoát vùng nguy hiểm định lượng, viết nhận định tự động, bóc tách BCTC từ PDF kiểm toán | Tính năng đột phá tạo lợi thế cạnh tranh |

---

## 4. Chi tiết Danh sách Chức năng Hệ thống

### 4.1. MUST-HAVE (Bắt buộc có ở bản phát hành chính thức — 12 chức năng)

#### Nhóm A: Tài khoản, Không gian riêng tư & Khởi đầu nhanh
* **[ ] M01 – Đăng ký, Đăng nhập & Bảo mật dữ liệu riêng tư:**
  * Hỗ trợ đăng ký tài khoản, đăng nhập nhanh (Email/Mật khẩu hoặc tài khoản Google), đăng xuất, đổi mật khẩu và khôi phục mật khẩu qua mã xác thực OTP.
  * Quản lý thông tin cá nhân/đơn vị công tác; cô lập dữ liệu Báo cáo tài chính bảo mật tuyệt đối theo từng tài khoản người dùng.
* **[ ] M02 – Hồ sơ Doanh nghiệp mẫu trải nghiệm ngay (Sample Onboarding):**
  * Cung cấp sẵn 3 hồ sơ doanh nghiệp mẫu tiêu biểu (*1 doanh nghiệp vững mạnh*, *1 doanh nghiệp đang suy giảm ngầm*, *1 doanh nghiệp nguy cơ phá sản cao*).
  * Cho phép người dùng mới trải nghiệm toàn bộ giao diện phân tích chỉ trong 30 giây ngay lần đầu đăng nhập trước khi tải dữ liệu thật.

#### Nhóm B: Quản lý Doanh nghiệp & Nhập liệu Kế toán Thân thiện
* **[ ] M03 – Quản lý Danh bạ Doanh nghiệp:**
  * Tạo mới, xem chi tiết, cập nhật, lưu trữ và tìm kiếm nhanh doanh nghiệp theo Tên công ty, Mã số thuế hoặc Mã chứng khoán.
  * Khai báo thông tin phân loại nghiệp vụ (*Ngành nghề hoạt động*, *Loại hình sản xuất/thương mại - dịch vụ*, *Đã niêm yết/Chưa niêm yết*) và gắn thẻ quản lý (*Khách hàng*, *Nhà cung cấp*, *Đối thủ*, *Danh mục đầu tư*).
* **[ ] M04 – Nhập Báo cáo Tài chính chuẩn Kế toán Việt Nam (Biểu mẫu & Excel):**
  * Cung cấp biểu mẫu Excel chuẩn hóa theo mã số chỉ tiêu quen thuộc của **Thông tư 200** và **Thông tư 133** để kế toán tải lên nhanh chóng.
  * Giao diện nhập trực tiếp trên web chia theo từng phần rõ ràng (*Bảng cân đối kế toán*, *Kết quả hoạt động kinh doanh*, *Lưu chuyển tiền tệ*), hỗ trợ chọn đơn vị tiền tệ (*Đồng / Triệu đồng / Tỷ đồng*), tự động cộng tổng các chỉ tiêu cấp cha và hỗ trợ **Lưu nháp**.
* **[ ] M05 – Kiểm tra Cân đối Kế toán & Chuẩn hóa số liệu tự động:**
  * Tự động rà soát tính hợp lệ kế toán ngay khi nhập hoặc tải file (ví dụ: đối chiếu *Tổng Tài sản* và *Tổng Nguồn vốn*, khớp số dư *Tiền và tương đương tiền cuối kỳ*), hiển thị cảnh báo rõ ràng tại dòng bị lệch để người dùng chỉnh sửa.
  * Tự động xử lý ngầm các trường hợp đặc thù trong tài chính như mẫu số bằng $0$ hoặc doanh nghiệp bị âm vốn chủ sở hữu để không làm sai lệch kết quả đánh giá.

#### Nhóm C: Đánh giá Sức khỏe Tài chính & Dự báo Nguy cơ Phá sản
* **[ ] M06 – Thẻ Điểm Sức Khỏe Tổng Hợp (Thang 0–100) & Xếp hạng 4 cấp độ:**
  * Quy đổi kết quả phân tích thành **1 Điểm Sức Khỏe Tài Chính duy nhất từ 0 đến 100** đặt tại vị trí trung tâm.
  * Phân loại trực quan theo 4 mức màu sắc chuẩn tín dụng: **Vững mạnh (Xanh lá)** – **Ổn định (Xanh dương)** – **Cần theo dõi sát (Vàng cam)** – **Nguy cơ khủng hoảng cao (Đỏ)**.
* **[ ] M07 – Dự báo Nguy cơ Kiệt quệ Tài chính 12 tháng tới & Độ tin cậy:**
  * Hiển thị tỷ lệ phần trăm nguy cơ rơi vào mất khả năng thanh toán / phá sản trong vòng 12 tháng tới.
  * Cung cấp chỉ báo **Độ tin cậy của kết quả đánh giá** dựa trên mức độ đồng thuận ngầm giữa 4 mô hình học máy (*Logistic Regression, Random Forest, XGBoost, LightGBM*).
* **[ ] M08 – Thước đo Altman Z-Score chuẩn Tài chính Quốc tế:**
  * Tự động áp dụng biến thể công thức phù hợp với loại hình doanh nghiệp và biểu diễn trực quan vị trí của công ty trên thanh thước đo 3 vùng (*Vùng An toàn – Vùng Xám – Vùng Nguy hiểm*) làm cơ sở đối chiếu quen thuộc cho giới tài chính.
* **[ ] M09 – Bức tranh 5 Trụ cột Sức khỏe Tài chính:**
  * Hệ thống hóa 20–25 chỉ số tài chính cốt lõi thành 5 trụ cột trên biểu đồ Radar và thẻ tóm tắt: *(1) Khả năng thanh toán ngắn hạn*, *(2) Cơ cấu vốn & Áp lực nợ vay*, *(3) Khả năng sinh lời*, *(4) Hiệu quả luân chuyển vốn*, *(5) Sức mạnh dòng tiền thực*.
  * Tích hợp hộp chú giải ngắn gọn giải thích ý nghĩa kinh tế và ngưỡng tham chiếu tốt/xấu ngay khi người dùng di chuột vào từng chỉ số.
* **[ ] M10 – Phân tích "Điểm Tựa & Điểm Nghẽn Tài Chính" (Giải thích nguyên nhân minh bạch):**
  * Liệt kê rõ tối đa 5 yếu tố tích cực đang bảo vệ doanh nghiệp và 5 yếu tố tiêu cực đang kéo điểm sức khỏe đi xuống mạnh nhất.
  * Diễn đạt hoàn toàn bằng ngôn ngữ tài chính dễ hiểu kèm mức độ tác động cụ thể (ví dụ: *"Áp lực nợ vay ngắn hạn vượt tài sản ngắn hạn làm giảm 16 điểm sức khỏe"*).
* **[ ] M11 – Biểu đồ Lịch sử Diễn biến Sức khỏe đa kỳ (3–5 năm):**
  * Lưu trữ kết quả đánh giá theo từng quý/năm và trực quan hóa xu hướng biến động của Điểm sức khỏe, Doanh thu – Lợi nhuận, Đòn bẩy nợ và Nguy cơ phá sản qua thời gian.
* **[ ] M12 – Xuất Báo cáo Thẩm định Tài chính chuẩn PDF:**
  * Tạo báo cáo PDF thiết kế chuyên nghiệp gồm trang tóm tắt điều hành (*Executive Summary*), điểm số tổng hợp, biểu đồ 5 trụ cột, bảng chỉ số chi tiết và các cảnh báo trọng tâm để in ấn hoặc trình ký.

---

### 4.2. SHOULD-HAVE (Nên có để sản phẩm sắc bén & sát thực tế — 06 chức năng)

* **[ ] S01 – So sánh Vị thế Doanh nghiệp với Trung bình Ngành:**
  * Đặt các chỉ số tài chính của doanh nghiệp cạnh mặt bằng chung của ngành tương ứng (*Thuộc nhóm 25% tốt nhất ngành / Ngang mức trung bình ngành / Thấp hơn trung bình ngành*) để đánh giá công bằng đặc thù đòn bẩy nợ giữa các lĩnh vực khác nhau.
* **[ ] S02 – Cảnh báo sớm Chuỗi suy giảm ngầm kéo dài:**
  * Tự động tính toán tốc độ thay đổi giữa các kỳ liên tiếp và phát tín hiệu cảnh báo sớm đối với các dấu hiệu suy thoái âm ỉ (ví dụ: *Biên lợi nhuận gộp thu hẹp 3 kỳ liên tiếp* hoặc *Dòng tiền kinh doanh âm kéo dài dù lợi nhuận kế toán vẫn dương*).
* **[ ] S03 – Thẩm định Hàng loạt qua Excel (Batch Assessment):**
  * Cho phép tải lên một tệp Excel chứa dữ liệu của hàng chục hoặc hàng trăm doanh nghiệp cùng lúc; hệ thống xử lý nền, xếp hạng danh sách ưu tiên các công ty có rủi ro cao nhất và hỗ trợ xuất bảng tổng hợp ra Excel.
* **[ ] S04 – Danh sách Theo dõi (Watchlist) & Thông báo Biến động:**
  * Cho phép đánh dấu các doanh nghiệp quan trọng vào danh sách giám sát trên trang chủ và tự động gửi cảnh báo (trên ứng dụng hoặc qua Email) khi số liệu kỳ mới khiến doanh nghiệp tụt hạng sức khỏe nghiêm trọng.
* **[ ] S05 – Lựa chọn Chế độ Thẩm định theo Khẩu vị Rủi ro:**
  * Cung cấp tùy chọn góc nhìn đánh giá phù hợp với mục đích kinh doanh thực tế: **Chế độ Thận trọng** (ưu tiên phát hiện sớm mọi rủi ro tiềm ẩn khi cấp tín dụng/bán chịu lớn) và **Chế độ Tiêu chuẩn** (dành cho khám sức khỏe định kỳ).
* **[ ] S06 – Sổ tay Ghi chú Thẩm định & Đính kèm Chứng từ:**
  * Cho phép chuyên viên ghi chú bổ sung các thông tin thực tế ngoài báo cáo tài chính (tình hình thị trường, tài sản đảm bảo, uy tín ban lãnh đạo) và lưu đính kèm tài liệu liên quan theo từng kỳ đánh giá.

---

### 4.3. COULD-HAVE (Tính năng nâng tầm trải nghiệm tư vấn — 05 chức năng)

* **[ ] C01 – Thanh trượt Giả lập Kịch bản Kinh doanh ("Nếu... thì sao?"):**
  * Cho phép người dùng kéo thanh trượt điều chỉnh giả định các biến số kinh doanh quen thuộc (tăng/giảm Doanh thu theo tỷ lệ %, thay đổi Lãi suất vay, giải phóng Hàng tồn kho, thu hồi Khoản phải thu) và quan sát Điểm sức khỏe cùng Nguy cơ phá sản cập nhật tức thì.
* **[ ] C02 – Đèn báo Độ tin cậy Số liệu Kế toán:**
  * Tự động đối chiếu sự bất cân xứng giữa lợi nhuận trên sổ sách và dòng tiền thực tế để đưa ra lưu ý chuyên môn khi phát hiện dấu hiệu số liệu báo cáo thiếu tính bền vững hoặc có biến động hạch toán bất thường.
* **[ ] C03 – So sánh Trực diện 2–3 Doanh nghiệp trên cùng màn hình:**
  * Đặt song song hồ sơ sức khỏe tài chính của nhiều đối tác, nhà cung cấp hoặc mã cổ phiếu để hỗ trợ lựa chọn phương án hợp tác/đầu tư an toàn nhất.
* **[ ] C04 – Khung Khuyến nghị Hành động Quản trị Rủi ro tham khảo:**
  * Đề xuất gợi ý ứng xử thương mại tương ứng với từng phân vùng rủi ro (ví dụ: *Đủ điều kiện mở rộng hạn mức công nợ*, *Nên giữ nguyên hạn mức và rà soát hàng quý*, hoặc *Cần yêu cầu thanh toán trả trước / bảo lãnh thanh toán*).
* **[ ] C05 – Chia sẻ Báo cáo Trực tuyến Bảo mật:**
  * Tạo liên kết xem báo cáo trực tuyến có đặt mật khẩu và thời hạn hiệu lực để gửi nhanh cho Ban Giám đốc, đối tác hoặc hội đồng đầu tư mà không cần gửi tệp đính kèm thủ công.

---

### 4.4. WOULD-HAVE / INNOVATION (Điểm khác biệt đột phá cho sản phẩm — 04 chức năng)

* **[ ] W01 – Gợi ý Lộ trình Cải thiện Tài chính Định lượng (Thoát vùng nguy hiểm):**
  * Tự động tính toán mức điều chỉnh khả thi tối thiểu trên các khoản mục tài chính có thể kiểm soát được để giúp doanh nghiệp nâng hạng sức khỏe lên vùng an toàn (ví dụ: *"Cần cơ cấu giảm khoảng 2,5 tỷ đồng nợ ngắn hạn hoặc rút ngắn kỳ thu tiền bình quân thêm 15 ngày để đưa điểm sức khỏe vượt mốc 65"*).
* **[ ] W02 – Tự động Tổng hợp "Bản Nhận định Tài chính Chuyên gia":**
  * Chuyển hóa toàn bộ kết quả chấm điểm, xu hướng đa kỳ, vị thế ngành và các điểm tựa/điểm nghẽn thành một bản nhận định phân tích mạch lạc bằng tiếng Việt chuẩn văn phong tài chính doanh nghiệp.
* **[ ] W03 – Tải trực tiếp Báo cáo Kiểm toán PDF tự động trích xuất số liệu:**
  * Hỗ trợ kéo-thả tệp PDF Báo cáo tài chính đã kiểm toán; công cụ nhận diện thông minh tự động điền số liệu vào đúng các chỉ tiêu trên biểu mẫu để người dùng kiểm tra nhanh trước khi bấm đánh giá.
* **[ ] W04 – Dự báo Tầm nhìn Đa kỳ hạn (Ngắn hạn 1 năm & Trung hạn 2–3 năm):**
  * Tách biệt rủi ro mất thanh khoản tức thời trong 12 tháng tới với nguy cơ suy thoái cấu trúc tài chính trong 2–3 năm tiếp theo, giúp định hình chiến lược xử lý ngắn hạn và tái cấu trúc dài hạn chính xác hơn.

---

## 5. Tiêu chuẩn Trải nghiệm Người dùng (UX Rules) Bắt buộc khi Go-Live

1. **Quy tắc 3 giây ở màn hình Tổng quan:** Ngay khi mở kết quả của một doanh nghiệp, người dùng phải nắm bắt được ngay kết luận cốt lõi trong 3 giây đầu tiên gồm: *Điểm sức khỏe (0–100)*, *Nhãn xếp hạng màu sắc*, *Nguy cơ khủng hoảng (%)* và *3 nhận định quan trọng nhất*. Bảng chi tiết 25 chỉ số được sắp xếp gọn ở phần xem sâu bên dưới.
2. **Không hiển thị con số "trơ trọi" thiếu ngữ cảnh:** Mọi chỉ số tài chính hiển thị trên màn hình đều phải đi kèm đánh giá trạng thái, so sánh với kỳ trước và tham chiếu chuẩn ngành để người không chuyên sâu vẫn hiểu ngay con số đó đang tốt hay xấu.
3. **Tách biệt 100% Vận hành Kỹ thuật AI khỏi Ứng dụng Khách hàng:** Toàn bộ quy trình huấn luyện mô hình, xử lý mất cân bằng dữ liệu, đánh giá độ chính xác và quản lý phiên bản của *Logistic Regression, Random Forest, XGBoost, LightGBM* được đóng gói thành quy trình kỹ thuật nội bộ phía máy chủ, đảm bảo giao diện sản phẩm luôn tinh gọn, chuyên nghiệp và đáng tin cậy.