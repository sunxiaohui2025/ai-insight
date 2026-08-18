import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Snackbar,
  Alert,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import BoltIcon from '@mui/icons-material/Bolt';
import StarIcon from '@mui/icons-material/Star';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { modelApi } from '../../services/api';
import { LLMModel, LLMModelInput, ModelTestResult, PathStyle, ProviderPreset } from '../../types';

interface FormState extends LLMModelInput {
  id?: number;
}

const emptyForm: FormState = {
  name: '',
  provider: 'openai',
  model_id: '',
  api_base_url: '',
  api_key: '',
  path_style: 'openai',
  max_tokens: 4096,
  temperature: 0,
  enabled: 1,
};

const PATH_STYLE_OPTIONS: { value: PathStyle; label: string; hint: string }[] = [
  { value: 'openai', label: 'OpenAI 兼容', hint: '{地址}/chat/completions' },
  { value: 'anthropic', label: 'Anthropic Messages', hint: '{地址}/messages' },
  { value: 'model-in-path', label: '模型名在路径中', hint: '{地址}/{模型ID}/v1/chat/completions' },
];

const Models: React.FC = () => {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [presets, setPresets] = useState<ProviderPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [draftResult, setDraftResult] = useState<ModelTestResult | null>(null);
  const [rowTesting, setRowTesting] = useState<number | null>(null);
  const [toast, setToast] = useState<{ msg: string; severity: 'success' | 'error' } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<LLMModel | null>(null);

  const isEditing = form.id !== undefined;

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [modelsRes, presetsRes] = await Promise.all([
        modelApi.getModels(),
        modelApi.getPresets(),
      ]);
      setModels(modelsRes.data || []);
      setPresets(presetsRes.data || []);
    } catch (error) {
      setToast({ msg: '加载模型列表失败', severity: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setForm(emptyForm);
    setDraftResult(null);
    setDialogOpen(true);
  };

  const openEdit = (model: LLMModel) => {
    setForm({
      id: model.id,
      name: model.name,
      provider: model.provider,
      model_id: model.model_id,
      api_base_url: model.api_base_url,
      api_key: '', // 留空表示不修改已保存的密钥
      path_style: model.path_style,
      max_tokens: model.max_tokens,
      temperature: model.temperature,
      enabled: model.enabled,
    });
    setDraftResult(null);
    setDialogOpen(true);
  };

  // 选择供应商预设时带出地址与调用风格
  const applyPreset = (providerKey: string) => {
    const preset = presets.find((p) => p.provider === providerKey);
    if (!preset) return;
    setForm((prev) => ({
      ...prev,
      provider: preset.provider,
      api_base_url: preset.api_base_url,
      path_style: preset.path_style,
      model_id: preset.models[0] || prev.model_id,
      name: prev.name || preset.label,
    }));
    setDraftResult(null);
  };

  const currentPreset = presets.find((p) => p.provider === form.provider);

  const handleTestDraft = async () => {
    if (!form.model_id || !form.api_base_url) {
      setToast({ msg: '请先填写模型 ID 与 API 地址', severity: 'error' });
      return;
    }
    try {
      setTesting(true);
      setDraftResult(null);
      const res = await modelApi.testDraft(form);
      setDraftResult(res.data);
    } catch (error: any) {
      setDraftResult({
        ok: false,
        latency_ms: 0,
        url: '',
        message: error?.response?.data?.detail || '测试请求失败',
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!form.name?.trim() || !form.model_id?.trim() || !form.api_base_url?.trim()) {
      setToast({ msg: '名称、模型 ID、API 地址均为必填', severity: 'error' });
      return;
    }
    try {
      setSaving(true);
      const payload: LLMModelInput = { ...form };
      if (!payload.api_key) delete payload.api_key; // 编辑时不覆盖原密钥
      if (isEditing) {
        await modelApi.updateModel(form.id!, payload);
      } else {
        await modelApi.createModel(payload);
      }
      setDialogOpen(false);
      setToast({ msg: isEditing ? '已保存修改' : '已新增模型', severity: 'success' });
      load();
    } catch (error: any) {
      setToast({ msg: error?.response?.data?.detail || '保存失败', severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleTestRow = async (model: LLMModel) => {
    try {
      setRowTesting(model.id);
      const res = await modelApi.testModel(model.id);
      setToast({
        msg: `${model.name}：${res.data.message}`,
        severity: res.data.ok ? 'success' : 'error',
      });
      load();
    } catch (error: any) {
      setToast({ msg: error?.response?.data?.detail || '测试失败', severity: 'error' });
    } finally {
      setRowTesting(null);
    }
  };

  const handleSetDefault = async (model: LLMModel) => {
    try {
      await modelApi.setDefault(model.id);
      setToast({ msg: `已将「${model.name}」设为默认模型`, severity: 'success' });
      load();
    } catch (error: any) {
      setToast({ msg: error?.response?.data?.detail || '设置失败', severity: 'error' });
    }
  };

  const handleToggle = async (model: LLMModel) => {
    try {
      await modelApi.toggleModel(model.id);
      load();
    } catch (error: any) {
      setToast({ msg: error?.response?.data?.detail || '操作失败', severity: 'error' });
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await modelApi.deleteModel(confirmDelete.id);
      setToast({ msg: `已删除「${confirmDelete.name}」`, severity: 'success' });
      setConfirmDelete(null);
      load();
    } catch (error: any) {
      setToast({ msg: error?.response?.data?.detail || '删除失败', severity: 'error' });
    }
  };

  const renderTestStatus = (model: LLMModel) => {
    if (model.last_test_ok === 1) {
      return (
        <Tooltip title={`${model.last_test_message}（${model.last_tested_at.slice(0, 19)}）`}>
          <Chip
            size="small"
            icon={<CheckCircleIcon />}
            label="连通"
            color="success"
            variant="outlined"
          />
        </Tooltip>
      );
    }
    if (model.last_test_ok === 0) {
      return (
        <Tooltip title={model.last_test_message}>
          <Chip size="small" icon={<ErrorIcon />} label="失败" color="error" variant="outlined" />
        </Tooltip>
      );
    }
    return <Chip size="small" label="未测试" variant="outlined" />;
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
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            模型管理
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            配置文章解读所使用的大模型。标记为默认的模型会被 Agent 与摘要生成调用。
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          新增模型
        </Button>
      </Box>

      <Paper variant="outlined">
        {models.length === 0 ? (
          <Box sx={{ py: 8, textAlign: 'center' }}>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              还没有配置任何模型
            </Typography>
            <Button variant="outlined" startIcon={<AddIcon />} onClick={openCreate}>
              添加第一个模型
            </Button>
          </Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>名称</TableCell>
                <TableCell>供应商</TableCell>
                <TableCell>模型 ID</TableCell>
                <TableCell>API 地址</TableCell>
                <TableCell align="center">密钥</TableCell>
                <TableCell align="center">状态</TableCell>
                <TableCell align="center">启用</TableCell>
                <TableCell align="right">操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {models.map((model) => (
                <TableRow key={model.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      {model.name}
                      {model.is_default === 1 && (
                        <Chip size="small" label="默认" color="primary" sx={{ height: 20 }} />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {model.provider}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                      {model.model_id}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ fontSize: 12, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}
                    >
                      {model.api_base_url}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    {model.has_api_key ? (
                      <Chip size="small" label="已设置" variant="outlined" />
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        无
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="center">{renderTestStatus(model)}</TableCell>
                  <TableCell align="center">
                    <Switch
                      size="small"
                      checked={model.enabled === 1}
                      onChange={() => handleToggle(model)}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="测试连通性">
                      <IconButton
                        size="small"
                        onClick={() => handleTestRow(model)}
                        disabled={rowTesting === model.id}
                      >
                        {rowTesting === model.id ? <CircularProgress size={16} /> : <BoltIcon fontSize="small" />}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={model.is_default ? '当前默认模型' : '设为默认'}>
                      <IconButton
                        size="small"
                        onClick={() => handleSetDefault(model)}
                        disabled={model.is_default === 1}
                      >
                        {model.is_default === 1 ? (
                          <StarIcon fontSize="small" color="primary" />
                        ) : (
                          <StarBorderIcon fontSize="small" />
                        )}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="编辑">
                      <IconButton size="small" onClick={() => openEdit(model)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="删除">
                      <IconButton size="small" onClick={() => setConfirmDelete(model)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      {/* 新增 / 编辑弹窗 */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{isEditing ? '编辑模型' : '新增模型'}</DialogTitle>
        <DialogContent dividers>
          <TextField
            select
            fullWidth
            label="供应商预设"
            value={form.provider || ''}
            onChange={(e) => applyPreset(e.target.value)}
            helperText="选择后自动填入 API 地址与调用风格，可继续手动调整"
            sx={{ mb: 2 }}
          >
            {presets.map((preset) => (
              <MenuItem key={preset.provider} value={preset.provider}>
                {preset.label}
              </MenuItem>
            ))}
          </TextField>

          <TextField
            fullWidth
            required
            label="显示名称"
            value={form.name || ''}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            sx={{ mb: 2 }}
          />

          <TextField
            fullWidth
            required
            label="模型 ID"
            value={form.model_id || ''}
            onChange={(e) => setForm({ ...form, model_id: e.target.value })}
            helperText="例如 gpt-4o、deepseek-chat"
            sx={{ mb: currentPreset && currentPreset.models.length > 0 ? 1 : 2 }}
          />

          {/* 预设模型快捷选择 */}
          {currentPreset && currentPreset.models.length > 0 && (
            <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 2 }}>
              {currentPreset.models.map((id) => (
                <Chip
                  key={id}
                  label={id}
                  size="small"
                  variant={form.model_id === id ? 'filled' : 'outlined'}
                  color={form.model_id === id ? 'primary' : 'default'}
                  onClick={() => setForm({ ...form, model_id: id })}
                />
              ))}
            </Box>
          )}

          <TextField
            fullWidth
            required
            label="API 地址"
            value={form.api_base_url || ''}
            onChange={(e) => setForm({ ...form, api_base_url: e.target.value })}
            sx={{ mb: 2 }}
          />

          <TextField
            fullWidth
            type="password"
            label="API 密钥"
            value={form.api_key || ''}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            autoComplete="new-password"
            helperText={isEditing ? '留空表示保留原有密钥' : '本地模型可留空'}
            sx={{ mb: 2 }}
          />

          <TextField
            select
            fullWidth
            label="调用风格"
            value={form.path_style || 'openai'}
            onChange={(e) => setForm({ ...form, path_style: e.target.value as PathStyle })}
            helperText={PATH_STYLE_OPTIONS.find((o) => o.value === form.path_style)?.hint}
            sx={{ mb: 2 }}
          >
            {PATH_STYLE_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </TextField>

          <Box sx={{ display: 'flex', gap: 2, mb: 1 }}>
            <TextField
              label="最大 tokens"
              type="number"
              value={form.max_tokens ?? 4096}
              onChange={(e) => setForm({ ...form, max_tokens: Number(e.target.value) })}
              sx={{ flex: 1 }}
            />
            <TextField
              label="温度"
              type="number"
              slotProps={{ htmlInput: { step: 0.1, min: 0, max: 2 } }}
              value={form.temperature ?? 0}
              onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })}
              sx={{ flex: 1 }}
            />
          </Box>

          <FormControlLabel
            control={
              <Switch
                checked={form.enabled === 1}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked ? 1 : 0 })}
              />
            }
            label="启用"
          />

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={testing ? <CircularProgress size={16} /> : <BoltIcon />}
              onClick={handleTestDraft}
              disabled={testing}
            >
              测试连接
            </Button>
            <Typography variant="caption" color="text.secondary">
              保存前可先验证配置是否可用
            </Typography>
          </Box>

          {draftResult && (
            <Alert severity={draftResult.ok ? 'success' : 'error'} sx={{ mt: 2 }}>
              <Typography variant="body2">{draftResult.message}</Typography>
              {draftResult.url && (
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5, wordBreak: 'break-all' }}>
                  请求地址：{draftResult.url}
                </Typography>
              )}
              {draftResult.reply && (
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                  模型回复：{draftResult.reply}
                </Typography>
              )}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 删除确认 */}
      <Dialog open={!!confirmDelete} onClose={() => setConfirmDelete(null)}>
        <DialogTitle>删除模型</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            确定要删除「{confirmDelete?.name}」吗？此操作不可撤销。
            {confirmDelete?.is_default === 1 && ' 删除后会自动把剩余的第一个模型设为默认。'}
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

export default Models;
