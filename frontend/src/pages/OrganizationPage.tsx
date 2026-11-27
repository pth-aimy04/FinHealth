import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Building2,
  Check,
  Copy,
  KeyRound,
  Plus,
  Shield,
  Trash2,
  UserPlus,
} from 'lucide-react';
import { api } from '@/lib/api';
import { ORG_ROLE_LABELS, formatDate } from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import type { OrgRole, OrganizationInviteCreated } from '@/types/api';
import {
  Button,
  EmptyState,
  ErrorState,
  PageHeader,
  Panel,
  PanelHeader,
  TableSkeleton,
} from '@/components/ui/Primitives';

export function OrganizationPage() {
  const queryClient = useQueryClient();
  const {
    user,
    organizations,
    activeOrg,
    switchOrg,
    refreshOrganizations,
  } = useAuth();

  const [newOrgName, setNewOrgName] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<OrgRole>('analyst');
  const [acceptToken, setAcceptToken] = useState('');
  const [lastCreatedInvite, setLastCreatedInvite] = useState<OrganizationInviteCreated | null>(
    null,
  );
  const [copiedToken, setCopiedToken] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isOrgAdmin = activeOrg?.role === 'org_admin';

  const membersQuery = useQuery({
    queryKey: ['organization', activeOrg?.id, 'members'],
    queryFn: () => api.getOrganizationMembers(activeOrg!.id),
    enabled: Boolean(user && activeOrg),
  });

  const invitesQuery = useQuery({
    queryKey: ['organization', activeOrg?.id, 'invites'],
    queryFn: () => api.getOrganizationInvites(activeOrg!.id),
    enabled: Boolean(user && activeOrg && isOrgAdmin),
  });

  const auditQuery = useQuery({
    queryKey: ['organization', activeOrg?.id, 'audit'],
    queryFn: () => api.getOrganizationAuditLogs(activeOrg!.id, 50, 0),
    enabled: Boolean(user && activeOrg && isOrgAdmin),
  });

  const createOrgMutation = useMutation({
    mutationFn: () => api.createOrganization(newOrgName.trim()),
    onSuccess: async (created) => {
      setErrorMessage(null);
      setStatusMessage(`Đã tạo tổ chức "${created.name}" và chuyển sang không gian mới.`);
      setNewOrgName('');
      await refreshOrganizations();
      await queryClient.invalidateQueries();
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Không thể tạo tổ chức.'),
  });

  const renameOrgMutation = useMutation({
    mutationFn: () => api.updateOrganization(activeOrg!.id, renameValue.trim()),
    onSuccess: async (updated) => {
      setErrorMessage(null);
      setStatusMessage(`Đã đổi tên tổ chức thành "${updated.name}".`);
      setRenameValue('');
      await refreshOrganizations();
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể đổi tên tổ chức.'),
  });

  const inviteMutation = useMutation({
    mutationFn: () => api.createOrganizationInvite(activeOrg!.id, inviteEmail.trim(), inviteRole),
    onSuccess: async (created) => {
      setErrorMessage(null);
      setLastCreatedInvite(created);
      setCopiedToken(false);
      setInviteEmail('');
      setStatusMessage(
        created.email_sent
          ? `Đã gửi lời mời tới ${created.email}.`
          : `Đã tạo mã mời cho ${created.email}. Sao chép mã mời bên dưới để gửi cho đồng nghiệp.`,
      );
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'invites'],
      });
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'audit'],
      });
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể tạo lời mời.'),
  });

  const revokeInviteMutation = useMutation({
    mutationFn: (inviteId: number) => api.revokeOrganizationInvite(activeOrg!.id, inviteId),
    onSuccess: async () => {
      setErrorMessage(null);
      setStatusMessage('Đã thu hồi lời mời.');
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'invites'],
      });
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'audit'],
      });
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể thu hồi lời mời.'),
  });

  const acceptInviteMutation = useMutation({
    mutationFn: () => api.acceptOrganizationInvite(acceptToken.trim()),
    onSuccess: async (res) => {
      setErrorMessage(null);
      setAcceptToken('');
      setStatusMessage(
        `Bạn đã tham gia tổ chức "${res.organization_name}" với vai trò ${ORG_ROLE_LABELS[res.role]}.`,
      );
      await refreshOrganizations();
      await switchOrg(res.organization_id);
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể chấp nhận mã mời.'),
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ memberUserId, role }: { memberUserId: number; role: OrgRole }) =>
      api.updateOrganizationMemberRole(activeOrg!.id, memberUserId, role),
    onSuccess: async () => {
      setErrorMessage(null);
      setStatusMessage('Đã cập nhật vai trò thành viên.');
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'members'],
      });
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'audit'],
      });
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể thay đổi vai trò.'),
  });

  const removeMemberMutation = useMutation({
    mutationFn: (memberUserId: number) =>
      api.removeOrganizationMember(activeOrg!.id, memberUserId),
    onSuccess: async () => {
      setErrorMessage(null);
      setStatusMessage('Đã gỡ thành viên khỏi tổ chức.');
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'members'],
      });
      await queryClient.invalidateQueries({
        queryKey: ['organization', activeOrg?.id, 'audit'],
      });
      await refreshOrganizations();
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể gỡ thành viên.'),
  });

  async function copyInviteToken(token: string) {
    try {
      await navigator.clipboard.writeText(token);
      setCopiedToken(true);
    } catch {
      setCopiedToken(false);
    }
  }

  if (!user) {
    return (
      <Panel ruled>
        <EmptyState
          title="Vui lòng đăng nhập để quản trị tổ chức"
          description="Không gian làm việc tổ chức giúp cô lập danh bạ doanh nghiệp, báo cáo tài chính và phân quyền thành viên."
          action={
            <Link to="/account" className="no-underline">
              <Button variant="primary">Đăng nhập / Đăng ký</Button>
            </Link>
          }
        />
      </Panel>
    );
  }

  return (
    <div className="space-y-5 animate-view">
      <PageHeader
        title="Quản trị Không gian Tổ chức"
        description="Chuyển đổi tổ chức, phân quyền thành viên (Quản trị / Chuyên viên / Người xem) và theo dõi nhật ký kiểm toán."
      />

      {statusMessage ? (
        <div
          role="status"
          className="px-4 py-2.5 rounded-[3px] border border-[var(--risk-low-border)] text-xs font-semibold bg-[var(--risk-low-bg)] text-[var(--risk-low-fg)]"
        >
          {statusMessage}
        </div>
      ) : null}
      {errorMessage ? (
        <div
          role="alert"
          className="px-4 py-2.5 rounded-[3px] border border-[var(--risk-critical-border)] text-xs font-semibold bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)]"
        >
          {errorMessage}
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        <Panel ruled className="lg:col-span-2 overflow-hidden">
          <PanelHeader
            title="Danh sách Không gian làm việc"
            description="Mỗi tổ chức có danh bạ doanh nghiệp và dữ liệu BCTC cô lập hoàn toàn."
          />
          <div className="divide-y divide-[var(--border-subtle)]">
            {organizations.map((org) => {
              const isCurrent = activeOrg?.id === org.id;
              return (
                <div
                  key={org.id}
                  className="px-5 py-3.5 flex flex-wrap items-center justify-between gap-3 text-[13px] hover:bg-[var(--bg-hover)]/45 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Building2
                      className="h-4 w-4 text-[var(--accent-primary)] shrink-0"
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <div className="font-bold text-[var(--text-primary)] truncate flex items-center gap-2">
                        <span>{org.name}</span>
                        {org.is_personal ? (
                          <span className="text-[10px] font-semibold uppercase tracking-[0.04em] px-1.5 py-0.5 rounded-[2px] bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                            Cá nhân
                          </span>
                        ) : null}
                      </div>
                      <div className="text-xs text-[var(--text-secondary)]">
                        {ORG_ROLE_LABELS[org.role]} · <span className="num">{org.member_count}</span> thành viên
                      </div>
                    </div>
                  </div>
                  {isCurrent ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[2px] border border-[var(--accent-border)] text-[11px] font-semibold bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                      <Check className="h-3 w-3" aria-hidden="true" />
                      Đang hoạt động
                    </span>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void switchOrg(org.id)}
                    >
                      Chuyển sang
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </Panel>

        <div className="min-w-0 space-y-5">
          <Panel className="overflow-hidden">
            <PanelHeader title="Tạo tổ chức mới" description="Tối đa 5 tổ chức hoạt động." />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createOrgMutation.mutate();
              }}
              className="p-4 space-y-3 text-xs"
            >
              <div>
                <label htmlFor="new-org-name" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Tên tổ chức / Phòng ban
                </label>
                <input
                  id="new-org-name"
                  type="text"
                  required
                  minLength={2}
                  maxLength={120}
                  value={newOrgName}
                  onChange={(e) => setNewOrgName(e.target.value)}
                  placeholder="VD: Phòng Thẩm định Tín dụng KHDN"
                  className="field-control"
                />
              </div>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                className="w-full"
                disabled={createOrgMutation.isPending}
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Tạo tổ chức
              </Button>
            </form>
          </Panel>

          <Panel className="overflow-hidden">
            <PanelHeader
              title="Tham gia bằng mã mời"
              description="Nhập mã mời nhận từ quản trị viên tổ chức."
            />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                acceptInviteMutation.mutate();
              }}
              className="p-4 space-y-3 text-xs"
            >
              <div>
                <label htmlFor="accept-invite-token" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Mã mời một lần
                </label>
                <input
                  id="accept-invite-token"
                  type="text"
                  required
                  minLength={16}
                  value={acceptToken}
                  onChange={(e) => setAcceptToken(e.target.value)}
                  placeholder="Dán mã mời tại đây..."
                  className="field-control font-mono"
                />
              </div>
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                className="w-full"
                disabled={acceptInviteMutation.isPending}
              >
                <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                Chấp nhận lời mời
              </Button>
            </form>
          </Panel>
        </div>
      </div>

      {activeOrg && isOrgAdmin ? (
        <Panel className="overflow-hidden">
          <PanelHeader
            title={`Cài đặt tổ chức: ${activeOrg.name}`}
            description="Chỉ Quản trị tổ chức mới có thể đổi tên và quản lý phân quyền."
          />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              renameOrgMutation.mutate();
            }}
            className="p-4 flex flex-col sm:flex-row gap-3 sm:items-end text-xs"
          >
            <div className="flex-1">
              <label htmlFor="rename-org-input" className="block font-semibold text-[var(--text-secondary)] mb-1">
                Đổi tên hiển thị tổ chức
              </label>
              <input
                id="rename-org-input"
                type="text"
                required
                minLength={2}
                maxLength={120}
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                placeholder={activeOrg.name}
                className="field-control"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm" disabled={renameOrgMutation.isPending}>
              Lưu tên mới
            </Button>
          </form>
        </Panel>
      ) : null}

      {activeOrg ? (
        <Panel ruled className="overflow-hidden">
          <PanelHeader
            title="Thành viên tổ chức"
            description={
              isOrgAdmin
                ? 'Thay đổi vai trò hoặc gỡ thành viên. Hệ thống luôn bảo vệ ít nhất 1 Quản trị tổ chức.'
                : 'Danh sách thành viên cùng không gian làm việc (chế độ chỉ xem).'
            }
          />
          {membersQuery.isLoading ? (
            <TableSkeleton rows={4} />
          ) : membersQuery.isError ? (
            <div className="p-4">
              <ErrorState
                message={
                  membersQuery.error instanceof Error
                    ? membersQuery.error.message
                    : 'Không thể tải danh sách thành viên.'
                }
                onRetry={() => void membersQuery.refetch()}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="ledger-table">
                <thead>
                  <tr>
                    <th>Thành viên</th>
                    <th>Email</th>
                    <th>Vai trò</th>
                    <th>Ngày tham gia</th>
                    {isOrgAdmin ? <th className="text-right">Thao tác</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {(membersQuery.data ?? []).map((member) => (
                    <tr key={member.user_id}>
                      <td>
                        <div className="font-semibold text-[var(--text-primary)]">
                          {member.display_name}
                          {member.user_id === user.id ? (
                            <span className="ml-1.5 text-[11px] font-normal text-[var(--text-muted)]">(Bạn)</span>
                          ) : null}
                        </div>
                        {member.job_title ? (
                          <div className="text-[11px] text-[var(--text-muted)]">
                            {member.job_title}
                          </div>
                        ) : null}
                      </td>
                      <td className="font-mono text-xs text-[var(--text-secondary)]">
                        {member.email}
                      </td>
                      <td>
                        {isOrgAdmin ? (
                          <select
                            aria-label={`Vai trò của ${member.display_name}`}
                            value={member.role}
                            disabled={updateRoleMutation.isPending}
                            onChange={(e) =>
                              updateRoleMutation.mutate({
                                memberUserId: member.user_id,
                                role: e.target.value as OrgRole,
                              })
                            }
                            className="field-control !h-8 !w-auto"
                          >
                            <option value="viewer">{ORG_ROLE_LABELS.viewer}</option>
                            <option value="analyst">{ORG_ROLE_LABELS.analyst}</option>
                            <option value="org_admin">{ORG_ROLE_LABELS.org_admin}</option>
                          </select>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)] text-xs font-semibold">
                            <Shield className="h-3 w-3 text-[var(--accent-primary)]" aria-hidden="true" />
                            {ORG_ROLE_LABELS[member.role]}
                          </span>
                        )}
                      </td>
                      <td className="text-[var(--text-secondary)] num">
                        {formatDate(member.joined_at)}
                      </td>
                      {isOrgAdmin ? (
                        <td className="text-right">
                          <Button
                            variant="danger"
                            size="sm"
                            aria-label={`Gỡ thành viên ${member.display_name}`}
                            disabled={removeMemberMutation.isPending}
                            onClick={() => removeMemberMutation.mutate(member.user_id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            Gỡ
                          </Button>
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      ) : null}

      {activeOrg && isOrgAdmin ? (
        <Panel className="overflow-hidden">
          <PanelHeader
            title="Mời thành viên mới"
            description="Mã mời có hiệu lực 72 giờ, chỉ dùng một lần và khớp đúng email người nhận."
          />
          <div className="p-4 space-y-4 text-xs">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                inviteMutation.mutate();
              }}
              className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end"
            >
              <div className="sm:col-span-6">
                <label htmlFor="invite-email" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Email đồng nghiệp
                </label>
                <input
                  id="invite-email"
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="analyst@company.vn"
                  className="field-control"
                />
              </div>
              <div className="sm:col-span-3">
                <label htmlFor="invite-role" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Vai trò phân quyền
                </label>
                <select
                  id="invite-role"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as OrgRole)}
                  className="field-control"
                >
                  <option value="viewer">{ORG_ROLE_LABELS.viewer}</option>
                  <option value="analyst">{ORG_ROLE_LABELS.analyst}</option>
                  <option value="org_admin">{ORG_ROLE_LABELS.org_admin}</option>
                </select>
              </div>
              <div className="sm:col-span-3">
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  disabled={inviteMutation.isPending}
                >
                  <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
                  Mời thành viên
                </Button>
              </div>
            </form>

            {lastCreatedInvite ? (
              <div className="p-3 rounded-[3px] bg-[var(--bg-header)] border border-[var(--border-strong)] flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold text-[var(--text-primary)]">
                    Mã mời một lần cho {lastCreatedInvite.email} ({ORG_ROLE_LABELS[lastCreatedInvite.role]})
                  </div>
                  <code className="block mt-1 font-mono text-[11px] break-all text-[var(--accent-primary)]">
                    {lastCreatedInvite.token}
                  </code>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void copyInviteToken(lastCreatedInvite.token)}
                >
                  {copiedToken ? (
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  {copiedToken ? 'Đã sao chép' : 'Sao chép mã'}
                </Button>
              </div>
            ) : null}

            {(invitesQuery.data ?? []).length > 0 ? (
              <div className="pt-3 border-t border-[var(--border-subtle)] space-y-2">
                <div className="font-bold text-[var(--text-secondary)] uppercase tracking-[0.04em] text-[11px]">
                  Lời mời đang chờ chấp nhận ({invitesQuery.data!.length})
                </div>
                <div className="divide-y divide-[var(--border-subtle)] border border-[var(--border-subtle)] rounded-[2px]">
                  {invitesQuery.data!.map((inv) => (
                    <div
                      key={inv.id}
                      className="flex flex-wrap items-center justify-between gap-2 py-2.5 px-3 bg-[var(--bg-surface)]"
                    >
                      <div>
                        <span className="font-mono font-semibold">{inv.email}</span>
                        <span className="mx-2 text-[var(--text-muted)]">·</span>
                        <span>{ORG_ROLE_LABELS[inv.role]}</span>
                        <span className="mx-2 text-[var(--text-muted)]">·</span>
                        <span className="text-[var(--text-muted)] num">
                          Hết hạn: {formatDate(inv.expires_at)}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => revokeInviteMutation.mutate(inv.id)}
                        disabled={revokeInviteMutation.isPending}
                      >
                        Thu hồi
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </Panel>
      ) : null}

      {activeOrg && isOrgAdmin ? (
        <Panel className="overflow-hidden">
          <PanelHeader
            title="Nhật ký kiểm toán tổ chức"
            description="Ghi nhận các thay đổi quản trị và phân quyền (không lưu mật khẩu hay số liệu BCTC)."
          />
          {auditQuery.isLoading ? (
            <TableSkeleton rows={4} />
          ) : (auditQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="Chưa có sự kiện kiểm toán"
              description="Các thao tác tạo tổ chức, mời hoặc thay đổi vai trò thành viên sẽ xuất hiện tại đây."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="ledger-table">
                <thead>
                  <tr>
                    <th>Thời gian</th>
                    <th>Hành động</th>
                    <th>Đối tượng</th>
                    <th>Kết quả</th>
                  </tr>
                </thead>
                <tbody>
                  {(auditQuery.data ?? []).map((entry) => (
                    <tr key={entry.id}>
                      <td className="num text-[var(--text-secondary)]">
                        {formatDate(entry.created_at)}
                      </td>
                      <td className="font-mono text-xs">{entry.action}</td>
                      <td className="font-mono text-xs text-[var(--text-secondary)]">
                        {entry.target}
                      </td>
                      <td className="text-[var(--risk-low-fg)] font-semibold">
                        {entry.outcome}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      ) : null}
    </div>
  );
}
