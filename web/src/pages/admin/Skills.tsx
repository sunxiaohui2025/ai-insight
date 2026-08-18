import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Paper,
  Snackbar,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DeleteIcon from '@mui/icons-material/Delete';
import ExtensionIcon from '@mui/icons-material/Extension';
import TerminalIcon from '@mui/icons-material/Terminal';
import { skillApi, SiteSkill } from '../../services/api';
import { Skill } from '../../types';

interface Toast {
  msg: string;
  severity: 'success' | 'error';
}

const SkillsPage: React.FC = () => {
  const [agentSkills, setAgentSkills] = useState<Skill[]>([]);
  const [siteSkills, setSiteSkills] = useState<SiteSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState<null | 'agent' | 'site'>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<
    | { kind: 'agent'; id: number; name: string }
    | { kind: 'site'; name: string; display: string }
    | null
  >(null);
  const [siteUpload, setSiteUpload] = useState<File | null>(null);
  const [agentUpload, setAgentUpload] = useState<File | null>(null);
  const siteBottomRef = useRef<HTMLInputElement>(null);
  const agentBottomRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [agentRes, siteRes] = await Promise.all([
        skillApi.getSkills(),
        skillApi.getSiteSkills(),
      ]);
      setAgentSkills(agentRes.data || []);
      setSiteSkills(siteRes.data || []);
    } catch (error: any) {
      setToast({ msg: error?.response?.data?.detail || '加载技能列表失败', severity: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (msg: string, severity: 'success' | 'error') => setToast({ msg, severity });

  const handleToggleAgent = async (skill: Skill) => {
    try {
      await skillApi.toggleSkill(skill.id, skill.enabled !== 1);
      flash(`已${skill.enabled === 1 ? '停用' : '启用'}「${skill.display_name}」`, 'success');
      load();
    } catch (error: any) {
      flash(error?.response?.data?.detail || '操作失败', 'error');
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      if (confirmDelete.kind === 'agent') {
        await skillApi.deleteSkill(confirmDelete.id);
        flash(`已删除提示技能「${confirmDelete.name}」`, 'success');
      } else {
        await skillApi.deleteSiteSkill(confirmDelete.name);
        flash(`已删除站点技能「${confirmDelete.display}」`, 'success');
      }
      setConfirmDelete(null);
      load();
    } catch (error: any) {
      flash(error?.response?.data?.detail || '删除失败', 'error');
    }
  };

  const uploadSiteFile = async (file: File, existed: boolean) => {
    if (!file) return;
    try {
      setUploading('site');
      const res = await skillApi.uploadSiteSkill(file);
      flash(
        `站点技能「${res.data?.display_name || file.name}」${existed ? '已更新（覆盖旧版本）' : '已上传'}，SKILL.md ${res.data?.instruction_chars ?? 0} 字`,
        'success'
      );
      load();
    } catch (error: any) {
      flash(error?.response?.data?.detail || '上传失败', 'error');
    } finally {
      setUploading(null);
    }
  };

  const uploadAgentFile = async (file: File) => {
    if (!file) return;
    try {
      setUploading('agent');
      const res = await skillApi.uploadSkill(file);
      const existed = agentSkills.some((s) => s.name === res.data?.name);
      flash(
        `提示技能「${res.data?.display_name || file.name}」${existed ? '已更新（覆盖同名）' : '已上传'}`,
        'success'
      );
      load();
    } catch (error: any) {
      flash(error?.response?.data?.detail || '上传失败', 'error');
    } finally {
      setUploading(null);
    }
  };

  // 站点技能行内“更新”：选中文件后立即覆盖该技能
  const onUpdateSiteFile = async (skill: SiteSkill, file: File) => {
    if (!file) return;
    try {
      setUploading('site');
      const res = await skillApi.uploadSiteSkill(file);
      const replaced = res.data?.name === skill.name;
      flash(
        `站点技能「${res.data?.display_name || file.name}」${replaced ? '更新成功' : '已上传（名称不匹配，作为新技能入库）'}`,
        'success'
      );
      load();
    } catch (error: any) {
      flash(error?.response?.data?.detail || '上传失败', 'error');
    } finally {
      setUploading(null);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Skill 管理
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          管理项目可用的技能：供 Agent 对话挂载的「提示技能」，以及可独立执行的「站点技能」（如 URL 提取）。上传同名的 ZIP 即可覆盖更新。
        </Typography>
      </Box>

      {/* ── 站点执行技能 ── */}
      <Typography variant="h6" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
        <TerminalIcon fontSize="small" color="primary" />
        站点执行技能（可运行 · 位于 server/skills）
      </Typography>
      <Paper variant="outlined" sx={{ mb: 4 }}>
        {siteSkills.length === 0 ? (
          <Typography color="text.secondary" sx={{ p: 3, textAlign: 'center' }}>
            还没有站点技能
          </Typography>
        ) : (
          siteSkills.map((skill) => (
            <Box
              key={skill.name}
              sx={{
                px: 3,
                py: 2,
                borderBottom: '1px solid',
                borderColor: 'divider',
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                '&:last-of-type': { borderBottom: 'none' },
              }}
            >
              <ExtensionIcon sx={{ color: 'primary.main' }} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography sx={{ fontWeight: 600 }}>{skill.display_name}</Typography>
                  <Chip size="small" label={`v${skill.version}`} variant="outlined" />
                  <Chip size="small" label={skill.entry} variant="outlined" color="secondary" sx={{ fontSize: 11 }} />
                </Box>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 0.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {skill.description || '（无描述）'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {skill.name} · SKILL.md {skill.has_skill_md ? `${skill.instruction_chars} 字` : '无'} · 更新于 {skill.updated_at}
                </Typography>
              </Box>
              <input
                type="file"
                accept=".zip"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = '';
                  if (f) onUpdateSiteFile(skill, f);
                }}
              />
              <Tooltip title={`更新技能「${skill.display_name}」（上传 ZIP 覆盖）`}>
                <span>
                  <Button
                    startIcon={<UploadFileIcon />}
                    onClick={(e) => {
                      const input = e.currentTarget.parentElement?.parentElement?.querySelector('input[type=file]') as HTMLInputElement;
                      input?.click();
                    }}
                    disabled={uploading !== null}
                  >
                    更新
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title="注意：删除站点技能会让依赖它的功能（如网页链接提取）不可用">
                <Button
                  color="error"
                  startIcon={<DeleteIcon />}
                  onClick={() =>
                    setConfirmDelete({ kind: 'site', name: skill.name, display: skill.display_name })
                  }
                >
                  删除
                </Button>
              </Tooltip>
            </Box>
          ))
        )}
        <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', display: 'flex', gap: 2, alignItems: 'center' }}>
          <input
            ref={siteBottomRef}
            type="file"
            accept=".zip"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setSiteUpload(f);
            }}
          />
          <Button
            variant="outlined"
            startIcon={<UploadFileIcon />}
            onClick={() => siteBottomRef.current?.click()}
            disabled={uploading !== null}
          >
            选择 ZIP 上传新站点技能
          </Button>
          {siteUpload && (
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              已选择：{siteUpload.name}
            </Typography>
          )}
          <Button
            variant="contained"
            onClick={() => {
              if (siteUpload) {
                const existed = siteSkills.some((s) => s.name === siteUpload.name);
                uploadSiteFile(siteUpload, existed);
              }
            }}
            disabled={!siteUpload || uploading !== null}
          >
            上传
          </Button>
        </Box>
      </Paper>

      {/* ── 对话提示技能 ── */}
      <Typography variant="h6" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
        <TerminalIcon fontSize="small" color="primary" />
        对话提示技能（供 Agent 会话挂载）
      </Typography>
      <Paper variant="outlined">
        {agentSkills.length === 0 ? (
          <Typography color="text.secondary" sx={{ p: 3, textAlign: 'center' }}>
            还没有提示技能
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>名称</TableCell>
                <TableCell>版本 / 类型</TableCell>
                <TableCell>描述</TableCell>
                <TableCell align="center">启用</TableCell>
                <TableCell align="right">操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {agentSkills.map((skill) => (
                <TableRow key={skill.id} hover>
                  <TableCell>
                    <Typography sx={{ fontWeight: 600 }}>{skill.display_name}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                      {skill.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={`v${skill.version}`} variant="outlined" />
                    <Chip size="small" label={skill.skill_type} variant="outlined" sx={{ ml: 0.5 }} />
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ maxWidth: 380, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    >
                      {skill.description || '—'}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Switch size="small" checked={skill.enabled === 1} onChange={() => handleToggleAgent(skill)} />
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      color="error"
                      size="small"
                      startIcon={<DeleteIcon />}
                      onClick={() =>
                        setConfirmDelete({ kind: 'agent', id: skill.id, name: skill.display_name })
                      }
                    >
                      删除
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', display: 'flex', gap: 2, alignItems: 'center' }}>
          <input
            ref={agentBottomRef}
            type="file"
            accept=".zip"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setAgentUpload(f);
            }}
          />
          <Button
            variant="outlined"
            startIcon={<UploadFileIcon />}
            onClick={() => agentBottomRef.current?.click()}
            disabled={uploading !== null}
          >
            选择 ZIP 上传提示技能
          </Button>
          {agentUpload && (
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              已选择：{agentUpload.name}
            </Typography>
          )}
          <Button
            variant="contained"
            onClick={() => agentUpload && uploadAgentFile(agentUpload)}
            disabled={!agentUpload || uploading !== null}
          >
            上传
          </Button>
        </Box>
      </Paper>

      {uploading && (
        <Box sx={{ mt: 1 }}>
          <LinearProgress />
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, textAlign: 'center' }}>
            正在上传…
          </Typography>
        </Box>
      )}

      {/* 删除确认 */}
      <Dialog open={!!confirmDelete} onClose={() => setConfirmDelete(null)}>
        <DialogTitle>删除技能</DialogTitle>
        <DialogContent>
          {confirmDelete?.kind === 'site' && (
            <Alert severity="warning" sx={{ mb: 1 }}>
              站点技能可被后端直接执行（例如网页链接的「技能提取」依赖它）。删除后将无法再运行。
            </Alert>
          )}
          <Typography variant="body2">
            确定要删除「{confirmDelete?.kind === 'site' ? confirmDelete.display : confirmDelete?.name}」吗？此操作不可撤销。
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(null)}>取消</Button>
          <Button color="error" variant="contained" onClick={handleDelete}>
            删除
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={!!toast}
        autoHideDuration={4000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        {toast ? (
          <Alert severity={toast.severity} onClose={() => setToast(null)}>
            {toast.msg}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Box>
  );
};

export default SkillsPage;
