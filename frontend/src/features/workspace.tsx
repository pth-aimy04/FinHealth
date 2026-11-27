import { useState, type ReactElement } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { request, mutate } from "../lib/api/client";
import {
  Empty,
  Evidence,
  PageTitle,
  Panel,
  QueryState,
  TableRegion,
} from "../components/shared";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
type Saved = {
  id: number;
  name: string;
  cik?: string;
  ticker?: string | null;
  filters?: Record<string, string | number>;
  model_version?: string;
  created_at?: string;
};
/** Owner-scoped saved research, with explicit deletion confirmation. */
export default function Workspace(): ReactElement {
  const { user, pending } = useSession();
  const client = useQueryClient();
  const [collection, setCollection] = useState("watchlist");
  const [selected, setSelected] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<Saved | null>(null);
  const query = useQuery({
    queryKey: ["workspace", collection],
    enabled: Boolean(user),
    queryFn: () => request<Saved[]>(`/me/${collection}`),
  });
  const detail = useQuery({
    queryKey: ["workspace-detail", selected],
    enabled: selected !== null,
    queryFn: () => request<unknown>(`/me/analyses/${selected}`),
  });
  const deletion = useMutation({
    mutationFn: (id: number) =>
      mutate(`/me/${collection}/${id}`, undefined, "DELETE"),
    onSuccess: async () => {
      setDeleting(null);
      await client.invalidateQueries({ queryKey: ["workspace", collection] });
    },
  });
  return (
    <>
      <PageTitle
        title="Workspace cá nhân"
        description="Doanh nghiệp theo dõi, bộ lọc đã lưu và kết quả phân tích thuộc riêng tài khoản của bạn."
      />
      {pending ? (
        <QueryState pending />
      ) : !user ? (
        <div className="notice">
          Đăng nhập để truy cập workspace riêng.{" "}
          <Link to="/account">Đăng nhập</Link>
        </div>
      ) : (
        <>
          <div className="account-tabs">
            {[
              ["watchlist", "Theo dõi"],
              ["screeners", "Bộ lọc đã lưu"],
              ["analyses", "Phân tích đã lưu"],
            ].map(([key, title]) => (
              <Button
                variant={collection === key ? "default" : "outline"}
                key={key}
                onClick={() => {
                  setCollection(key);
                  setSelected(null);
                }}
              >
                {title}
              </Button>
            ))}
          </div>
          <Panel
            title="Nghiên cứu của bạn"
            note="Tối đa 200 mục mỗi loại · chỉ lưu khi bạn chủ động yêu cầu"
          >
            <QueryState
              pending={query.isPending}
              error={query.error}
              retry={query.refetch}
            />
            {query.data?.length ? (
              <TableRegion name="Nghiên cứu đã lưu">
                <table>
                  <thead>
                    <tr>
                      <th>Tên</th>
                      <th>Nội dung</th>
                      <th>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.map((row) => (
                      <tr key={row.id}>
                        <td>{row.ticker ?? row.name}</td>
                        <td>
                          {collection === "watchlist"
                            ? row.name
                            : (row.model_version ??
                              JSON.stringify(row.filters))}
                        </td>
                        <td>
                          <div className="actions">
                            {collection === "watchlist" ? (
                              <Button asChild variant="outline">
                                <Link to={`/company/${row.cik}`}>
                                  Phân tích
                                </Link>
                              </Button>
                            ) : collection === "screeners" ? (
                              <Button variant="outline" asChild>
                                <Link
                                  to={`/screener?${new URLSearchParams(Object.entries(row.filters ?? {}).map(([key, value]) => [key, String(value)]))}`}
                                >
                                  Áp dụng bộ lọc
                                </Link>
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                onClick={() => setSelected(row.id)}
                              >
                                Đọc kết quả
                              </Button>
                            )}
                            <Button
                              variant="destructive"
                              onClick={() => setDeleting(row)}
                            >
                              Xóa
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableRegion>
            ) : (
              query.data && (
                <Empty message="Chưa có mục đã lưu. Bắt đầu từ sàng lọc, trang doanh nghiệp hoặc dự báo thủ công." />
              )
            )}
          </Panel>
          {selected !== null && (
            <Panel title="Phân tích đã lưu">
              <div className="panel-body">
                <QueryState
                  pending={detail.isPending}
                  error={detail.error}
                  retry={detail.refetch}
                />
                <Evidence data={detail.data} />
              </div>
            </Panel>
          )}
        </>
      )}
      <Dialog
        open={Boolean(deleting)}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Xóa mục đã lưu"
      >
        <p>Xóa “{deleting?.name}” khỏi workspace của bạn?</p>
        <QueryState error={deletion.error} />
        <div className="actions mt-6">
          <Button variant="outline" onClick={() => setDeleting(null)}>
            Hủy
          </Button>
          <Button
            variant="destructive"
            disabled={deletion.isPending}
            onClick={() => deleting && deletion.mutate(deleting.id)}
          >
            {deletion.isPending ? "Đang xóa…" : "Xóa mục"}
          </Button>
        </div>
      </Dialog>
    </>
  );
}
