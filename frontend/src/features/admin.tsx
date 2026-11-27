import { useState, type ReactElement } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useSession, type User } from "../app/session";
import { request, mutate } from "../lib/api/client";
import {
  Evidence,
  PageTitle,
  Panel,
  QueryState,
  TableRegion,
} from "../components/shared";
import { DataForm } from "../components/data-form";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
type Job = {
  id: number;
  status: string;
  identifier: string;
  stage: string;
  error_message?: string;
};
/** Administrative operations gated by role in the UI and enforced again by backend dependencies. */
export default function Admin(): ReactElement {
  const { user, pending } = useSession();
  const client = useQueryClient();
  const [tab, setTab] = useState("overview");
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [eventId, setEventId] = useState<number | null>(null);
  const [confirmation, setConfirmation] = useState<{
    title: string;
    path: string;
    payload: unknown;
    method?: string;
  } | null>(null);
  const authorized = user?.role === "admin";
  const overview = useQuery({
    queryKey: ["admin", "overview"],
    enabled: authorized,
    queryFn: () =>
      request<{
        database_connected: boolean;
        worker_enabled: boolean;
        email_configured: boolean;
        counts: Record<string, number>;
        last_success: string | null;
      }>("/admin/overview"),
  });
  const data = useQuery({
    queryKey: ["admin", tab, offset, status],
    enabled: authorized && tab === "audit",
    queryFn: () =>
      request<unknown[]>(
        `/admin/${tab}?offset=${offset}&limit=25${status && tab === "ingestion" ? `&status=${status}` : ""}`,
      ),
  });
  const users = useQuery({
    queryKey: ["admin-users", offset],
    enabled: authorized && tab === "users",
    queryFn: () => request<User[]>(`/admin/users?offset=${offset}&limit=25`),
  });
  const jobs = useQuery({
    queryKey: ["admin-jobs", offset, status],
    enabled: authorized && tab === "ingestion",
    queryFn: () =>
      request<Job[]>(
        `/admin/ingestion?offset=${offset}&limit=25${status ? `&status=${status}` : ""}`,
      ),
    refetchInterval: authorized && tab === "ingestion" ? 10_000 : false,
  });
  const events = useQuery({
    queryKey: ["admin-events", eventId],
    enabled: authorized && eventId !== null,
    queryFn: () => request<unknown[]>(`/admin/ingestion/${eventId}/events`),
  });
  const action = useMutation({
    mutationFn: async () => {
      if (confirmation)
        return mutate(
          confirmation.path,
          confirmation.payload,
          confirmation.method ?? "POST",
        );
    },
    onSuccess: async () => {
      setConfirmation(null);
      await client.invalidateQueries({
        predicate: (query) => String(query.queryKey[0]).startsWith("admin"),
      });
    },
  });
  return (
    <>
      <PageTitle
        title="Quản trị hệ thống"
        description="Trạng thái vận hành thực tế, tài khoản, tác vụ cập nhật SEC và nhật ký kiểm toán."
      />
      <QueryState pending={pending} />
      {!pending && !authorized ? (
        <div className="notice">
          Chỉ quản trị viên được phép truy cập.{" "}
          {user ? (
            "Tài khoản hiện tại không có quyền quản trị."
          ) : (
            <Link to="/account">Đăng nhập</Link>
          )}
        </div>
      ) : (
        authorized && (
          <>
            <div className="account-tabs">
              {[
                ["overview", "Vận hành"],
                ["users", "Người dùng"],
                ["ingestion", "Tác vụ SEC"],
                ["audit", "Audit"],
                ["training", "Huấn luyện"],
              ].map(([key, title]) => (
                <Button
                  key={key}
                  variant={tab === key ? "default" : "outline"}
                  onClick={() => {
                    setTab(key);
                    setOffset(0);
                  }}
                >
                  {title}
                </Button>
              ))}
              <Button
                variant="ghost"
                onClick={() =>
                  void client.invalidateQueries({
                    predicate: (query) =>
                      String(query.queryKey[0]).startsWith("admin"),
                  })
                }
              >
                Làm mới
              </Button>
            </div>
            <QueryState error={overview.error} retry={overview.refetch} />
            {tab === "overview" && (
              <Panel title="Kết nối & dịch vụ">
                <div className="panel-body">
                  <QueryState pending={overview.isPending} />
                  <Evidence data={overview.data} />
                </div>
              </Panel>
            )}
            {tab === "users" && (
              <Panel
                title="Quản lý người dùng"
                note="Không cho đổi role hoặc khóa quản trị viên qua giao diện"
              >
                <QueryState
                  pending={users.isPending}
                  error={users.error}
                  retry={users.refetch}
                />
                <TableRegion name="Danh sách tài khoản">
                  <table>
                    <thead>
                      <tr>
                        <th>Tên</th>
                        <th>Email</th>
                        <th>Quyền</th>
                        <th>Trạng thái</th>
                        <th>Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.data?.map((row) => (
                        <tr key={row.id}>
                          <td>{row.display_name}</td>
                          <td>{row.email}</td>
                          <td>{row.role}</td>
                          <td>
                            {row.active ? "Hoạt động" : "Đã khóa"} ·{" "}
                            {row.email_verified
                              ? "Đã xác thực"
                              : "Chưa xác thực"}
                          </td>
                          <td>
                            <Button
                              variant="outline"
                              disabled={row.role === "admin"}
                              onClick={() =>
                                setConfirmation({
                                  title: `${row.active ? "Khóa" : "Mở khóa"} ${row.email}`,
                                  path: `/admin/users/${row.id}`,
                                  payload: { active: !row.active },
                                  method: "PATCH",
                                })
                              }
                            >
                              {row.active ? "Khóa tài khoản" : "Mở khóa"}
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableRegion>
              </Panel>
            )}
            {tab === "ingestion" && (
              <>
                <Panel
                  title="Yêu cầu cập nhật SEC"
                  note="Chỉ chạy khi quản trị viên chủ động gửi. Không dựng phần trăm tiến độ giả."
                >
                  <div className="panel-body">
                    {!overview.data?.worker_enabled && (
                      <p className="notice">
                        Worker đang tắt. Không thể gửi tác vụ hàng đợi.
                      </p>
                    )}
                    <DataForm
                      fields={[
                        {
                          name: "identifiers",
                          label:
                            "Ticker/CIK (tối đa 10, cách nhau bằng dấu phẩy)",
                          required: true,
                          max: 320,
                        },
                      ]}
                      submit="Chuẩn bị yêu cầu cập nhật"
                      onSubmit={async (values) => {
                        const ids = values.identifiers
                          .split(",")
                          .map((value) => value.trim())
                          .filter(Boolean);
                        if (!overview.data?.worker_enabled)
                          throw new Error("Worker đang tắt.");
                        if (
                          ids.length > 10 ||
                          ids.some((id) => !/^[A-Za-z0-9.-]{1,30}$/.test(id))
                        )
                          throw new Error("Nhập tối đa 10 ticker/CIK hợp lệ.");
                        for (const id of ids)
                          await mutate(`/ingestion/${encodeURIComponent(id)}`);
                        await jobs.refetch();
                        return "Đã gửi tác vụ. Theo dõi trạng thái bên dưới.";
                      }}
                    />
                  </div>
                </Panel>
                <Panel title="Lịch sử tác vụ">
                  <div className="panel-body">
                    <label>
                      Lọc trạng thái
                      <select
                        value={status}
                        onChange={(event) => {
                          setStatus(event.target.value);
                          setOffset(0);
                        }}
                      >
                        <option value="">Tất cả</option>
                        {["queued", "running", "succeeded", "failed"].map(
                          (value) => (
                            <option key={value}>{value}</option>
                          ),
                        )}
                      </select>
                    </label>
                  </div>
                  <QueryState
                    pending={jobs.isPending}
                    error={jobs.error}
                    retry={jobs.refetch}
                  />
                  <TableRegion name="Tác vụ cập nhật SEC">
                    <table>
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Doanh nghiệp</th>
                          <th>Trạng thái</th>
                          <th>Bước thực tế</th>
                          <th>Thao tác</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobs.data?.map((job) => (
                          <tr key={job.id}>
                            <td>{job.id}</td>
                            <td>{job.identifier}</td>
                            <td>{job.status}</td>
                            <td>{job.stage}</td>
                            <td>
                              <div className="actions">
                                <Button
                                  variant="outline"
                                  onClick={() => setEventId(job.id)}
                                >
                                  Sự kiện
                                </Button>
                                <Button
                                  variant="outline"
                                  disabled={
                                    job.status !== "failed" ||
                                    !overview.data?.worker_enabled
                                  }
                                  onClick={() =>
                                    setConfirmation({
                                      title: `Chạy lại tác vụ ${job.id}`,
                                      path: `/ingestion/${job.id}/retry`,
                                      payload: undefined,
                                    })
                                  }
                                >
                                  Chạy lại
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </TableRegion>
                </Panel>
                {eventId !== null && (
                  <Panel title={`Sự kiện tác vụ ${eventId}`}>
                    <div className="panel-body">
                      <QueryState
                        pending={events.isPending}
                        error={events.error}
                        retry={events.refetch}
                      />
                      <Evidence data={events.data} />
                    </div>
                  </Panel>
                )}
              </>
            )}
            {tab === "audit" && (
              <Panel
                title="Nhật ký kiểm toán"
                note="Chỉ đọc · không có thao tác xóa"
              >
                <div className="panel-body">
                  <QueryState
                    pending={data.isPending}
                    error={data.error}
                    retry={data.refetch}
                  />
                  <Evidence data={data.data} />
                </div>
              </Panel>
            )}
            {["users", "ingestion", "audit"].includes(tab) && (
              <div className="actions mb-6">
                <Button
                  variant="outline"
                  disabled={offset === 0}
                  onClick={() => setOffset((value) => Math.max(0, value - 25))}
                >
                  Trước
                </Button>
                <span className="small">Trang {offset / 25 + 1}</span>
                <Button
                  variant="outline"
                  disabled={
                    (tab === "users"
                      ? users.data?.length
                      : tab === "ingestion"
                        ? jobs.data?.length
                        : data.data?.length) !== 25
                  }
                  onClick={() => setOffset((value) => value + 25)}
                >
                  Sau
                </Button>
              </div>
            )}
            {tab === "training" && (
              <Panel
                title="Huấn luyện và công bố phiên bản"
                note="Tác vụ đồng bộ. Chỉ dùng panel đã lưu; thao tác sẽ tạo và kích hoạt mô hình mới."
              >
                <div className="panel-body">
                  <DataForm
                    fields={[
                      {
                        name: "model_version",
                        label: "Phiên bản mới bất biến",
                        required: true,
                        max: 64,
                        pattern: /^[A-Za-z0-9][A-Za-z0-9_.-]*$/,
                      },
                      {
                        name: "train_end_year",
                        label: "Năm kết thúc training",
                        type: "number",
                        integer: true,
                        required: true,
                        min: 1990,
                        max: 2100,
                      },
                      {
                        name: "validation_end_year",
                        label: "Năm kết thúc validation (tùy chọn)",
                        type: "number",
                        integer: true,
                        min: 1991,
                        max: 2100,
                      },
                      {
                        name: "imbalance_strategy",
                        label: "Mất cân bằng lớp",
                        type: "select",
                        defaultValue: "class_weight",
                        options: [
                          { value: "class_weight", label: "Class weight" },
                          { value: "smote", label: "SMOTE" },
                        ],
                      },
                    ]}
                    submit="Xem lại yêu cầu huấn luyện"
                    onSubmit={async (values) => {
                      if (
                        values.validation_end_year &&
                        Number(values.validation_end_year) <=
                          Number(values.train_end_year)
                      )
                        throw new Error(
                          "Năm validation phải sau năm training.",
                        );
                      setConfirmation({
                        title: "Huấn luyện và kích hoạt mô hình mới",
                        path: "/models/train",
                        payload: {
                          model_version: values.model_version,
                          train_end_year: Number(values.train_end_year),
                          imbalance_strategy: values.imbalance_strategy,
                          ...(values.validation_end_year
                            ? {
                                validation_end_year: Number(
                                  values.validation_end_year,
                                ),
                              }
                            : {}),
                        },
                      });
                      return "Yêu cầu đã sẵn sàng để xác nhận.";
                    }}
                  />
                </div>
              </Panel>
            )}
          </>
        )
      )}
      <Dialog
        open={Boolean(confirmation)}
        onOpenChange={(open) => {
          if (!open && !action.isPending) setConfirmation(null);
        }}
        title={confirmation?.title ?? "Xác nhận thao tác"}
      >
        <Evidence data={confirmation?.payload} />
        <QueryState error={action.error} />
        <div className="actions mt-6">
          <Button
            variant="outline"
            disabled={action.isPending}
            onClick={() => setConfirmation(null)}
          >
            Hủy
          </Button>
          <Button disabled={action.isPending} onClick={() => action.mutate()}>
            {action.isPending
              ? "Đang xử lý, không gửi lại…"
              : "Xác nhận thực hiện"}
          </Button>
        </div>
      </Dialog>
    </>
  );
}
