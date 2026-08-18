import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Chip,
  Alert,
  CircularProgress,
} from '@mui/material';
import { adminUserApi } from '../../services/api';

/** 后端 /api/v1/admin/users 返回的用户字段 */
interface AdminUser {
  id: number;
  email: string;
  name: string;
  status: 'pending' | 'approved' | 'disabled' | string;
  role: string;
  created_at: string;
  last_login_at?: string;
  article_count?: number;
  llm_count?: number;
  insight_events?: number;
  last_activity_at?: string;
}

const statusName: Record<string, string> = {
  pending: '待审批',
  approved: '已批准',
  disabled: '已停用',
};

const statusColor: Record<string, 'warning' | 'success' | 'default'> = {
  pending: 'warning',
  approved: 'success',
  disabled: 'default',
};

const ACTION_LABEL: Record<string, string> = {
  approved: '批准该用户',
  disabled: '停用该用户',
  pending: '重新设为待审批',
};

/**
 * 后台用户管理页（仅管理员可见）
 * - 普通用户自行注册后默认为「待审批」，由管理员在此批准后即可登录阅读文章
 * - 该页面只能调整用户状态，不能授予后台管理权限（角色仅由服务端引导创建）
 */
const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const load = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await adminUserApi.getUsers();
      setUsers(res.data as unknown as AdminUser[]);
    } catch (e: any) {
      setMsg({ type: 'error', text: e.response?.data?.detail || '加载用户失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const changeStatus = async (id: number, status: string) => {
    const label = ACTION_LABEL[status] || status;
    if (!window.confirm(`确定要${label}吗？`)) return;
    try {
      await adminUserApi.updateUserStatus(id, status);
      setMsg({ type: 'success', text: `已${label}` });
      await load();
    } catch (e: any) {
      setMsg({ type: 'error', text: e.response?.data?.detail || '操作失败' });
    }
  };

  const pending = users.filter((u) => u.status === 'pending').length;

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 600, mb: 1 }}>
        用户管理
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        普通用户自行注册后默认为「待审批」，由管理员批准后即可登录阅读文章。
        本后台仅限管理员管理，任何用户无法在此获得后台管理权限。
        {pending > 0 && (
          <Box component="span" sx={{ color: 'warning.main', fontWeight: 600 }}>
            {' '}当前有 {pending} 位待审批用户
          </Box>
        )}
      </Typography>

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      <Paper sx={{ overflow: 'auto' }}>
        {loading ? (
          <Box sx={{ textAlign: 'center', p: 5 }}>
            <CircularProgress />
          </Box>
        ) : users.length === 0 ? (
          <Box sx={{ textAlign: 'center', p: 5, color: 'text.secondary' }}>暂无用户</Box>
        ) : (
          <Table sx={{ minWidth: 720 }}>
            <TableHead>
              <TableRow>
                <TableCell>用户</TableCell>
                <TableCell>角色</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>注册时间</TableCell>
                <TableCell>最近登录</TableCell>
                <TableCell>使用记录</TableCell>
                <TableCell>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>
                    <b>{u.name}</b>
                    <br />
                    <span style={{ color: '#786d67' }}>{u.email}</span>
                  </TableCell>
                  <TableCell>{u.role === 'admin' ? '管理员' : '普通用户'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={statusName[u.status] || u.status}
                      color={statusColor[u.status] || 'default'}
                    />
                  </TableCell>
                  <TableCell>{u.created_at?.slice(0, 10)}</TableCell>
                  <TableCell>{u.last_login_at ? u.last_login_at.slice(0, 16).replace('T', ' ') : '未登录'}</TableCell>
                  <TableCell>
                    收藏 {u.article_count || 0} 篇 · AI {u.llm_count || 0} 次
                  </TableCell>
                  <TableCell>
                    {u.role === 'admin' ? (
                      <span style={{ color: '#786d67' }}>管理员</span>
                    ) : u.status === 'approved' ? (
                      <Button size="small" color="warning" onClick={() => changeStatus(u.id, 'disabled')}>
                        停用
                      </Button>
                    ) : (
                      <>
                        <Button
                          size="small"
                          color="success"
                          disabled={u.status === 'disabled'}
                          onClick={() => changeStatus(u.id, 'approved')}
                        >
                          批准
                        </Button>
                        {u.status === 'pending' && (
                          <Button
                            size="small"
                            color="error"
                            sx={{ ml: 1 }}
                            onClick={() => changeStatus(u.id, 'disabled')}
                          >
                            拒绝
                          </Button>
                        )}
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>
    </Box>
  );
};

export default UserManagement;
