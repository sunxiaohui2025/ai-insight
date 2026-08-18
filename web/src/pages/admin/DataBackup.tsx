import React, { useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Paper,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import BackupIcon from '@mui/icons-material/Backup';
import RestoreIcon from '@mui/icons-material/Restore';
import DownloadIcon from '@mui/icons-material/Download';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { dataBackupApi, DbImportResult } from '../../services/api';

interface Toast {
  msg: string;
  severity: 'success' | 'error' | 'warning';
}

const DataBackup: React.FC = () => {
  const [toast, setToast] = useState<Toast | null>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DbImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const flash = (msg: string, severity: Toast['severity']) => setToast({ msg, severity });

  const handleExport = async () => {
    try {
      setExporting(true);
      const blob = await dataBackupApi.exportDb();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const stamp = new Date()
        .toISOString()
        .replace(/[-:]/g, '')
        .replace(/T/, '-')
        .replace(/\..+/, '');
      a.download = `insight-backup-${stamp}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      flash('备份已下载（已排除大模型连接配置与 API Key）', 'success');
    } catch (error: any) {
      flash(error?.response?.data?.detail || '导出备份失败', 'error');
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async () => {
    if (!file) return;
    try {
      setImporting(true);
      setResult(null);
      const res = await dataBackupApi.importDb(file);
      setResult(res.data);
      if (res.data.ok) {
        flash('导入完成：业务数据已合并进当前库', 'success');
      } else {
        flash('导入部分完成，但存在错误，请见下方明细', 'warning');
      }
    } catch (error: any) {
      flash(error?.response?.data?.detail || '导入失败，请检查文件是否为 .db 备份', 'error');
    } finally {
      setImporting(false);
    }
  };

  const importedEntries = result ? Object.entries(result.imported) : [];

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          数据备份 / 导入
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          用于数据迁移与容灾。备份与导入均会<strong>排除大模型连接配置（llm_models，含 API Key）</strong>，
          请在新环境单独填写模型连接参数。
        </Typography>
      </Box>

      {/* ── 数据备份 ── */}
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <BackupIcon color="primary" />
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              数据备份（导出）
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            导出一个 <strong>.zip</strong> 备份包，包含全部业务数据（用户、文章、分类、板块、设置、事件、Agent 等）
            以及文章引用的媒体文件（标题图 / 正文图）。
            备份会自动剔除大模型连接地址与 API Key，安全用于迁移。
          </Typography>
          <Button variant="contained" startIcon={<DownloadIcon />} onClick={handleExport} disabled={exporting}>
            {exporting ? <CircularProgress size={20} color="inherit" /> : '下载备份 (.zip)'}
          </Button>
        </CardContent>
      </Card>

      {/* ── 数据导入 ── */}
      <Card variant="outlined">
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <RestoreIcon color="primary" />
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              数据导入（恢复 / 迁移）
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            上传一个 <strong>.zip</strong> 备份包（或 .db 文件），按主键<strong>合并</strong>进当前库（不会清空已有数据，同名主键会覆盖）。
            会一并恢复文章引用的媒体文件（标题图 / 正文图），不会写入大模型连接配置。可直接用于把旧环境迁移到新部署。
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            提示：含大模型配置的库也可使用，迁移时 llm_models 会被自动跳过。
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip,.db,.sqlite,.sqlite3"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setFile(f);
              }}
            />
            <Button variant="outlined" startIcon={<UploadFileIcon />} onClick={() => fileInputRef.current?.click()} disabled={importing}>
              选择备份文件
            </Button>
            {file && <Typography variant="body2" color="text.secondary">{file.name}</Typography>}
            <Button
              variant="contained"
              color="secondary"
              startIcon={<RestoreIcon />}
              onClick={handleImport}
              disabled={!file || importing}
            >
              {importing ? <CircularProgress size={20} color="inherit" /> : '导入备份'}
            </Button>
          </Box>

          {result && (
            <Paper variant="outlined" sx={{ mt: 3 }}>
              <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography sx={{ fontWeight: 600 }}>导入结果</Typography>
                {result.ok ? (
                  <Chip size="small" color="success" label="完成" sx={{ ml: 1 }} />
                ) : (
                  <Chip size="small" color="warning" label="部分失败" sx={{ ml: 1 }} />
                )}
                <Chip size="small" variant="outlined" label={`已排除: ${result.excluded.join(', ') || '无'}`} sx={{ ml: 1 }} />
                {typeof result.media_restored === 'number' && (
                  <Chip
                    size="small"
                    color={result.media_restored > 0 ? 'primary' : 'default'}
                    label={`恢复媒体文件: ${result.media_restored} 个（标题图/正文图）`}
                    sx={{ ml: 1 }}
                  />
                )}
              </Box>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>数据表</TableCell>
                    <TableCell align="right">导入行数</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {importedEntries.map(([table, count]) => (
                    <TableRow key={table} hover>
                      <TableCell sx={{ fontFamily: 'monospace' }}>{table}</TableCell>
                      <TableCell align="right">{count}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Paper>
          )}

          {result && result.errors.length > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              <Typography sx={{ fontWeight: 600 }}>以下表导入失败：</Typography>
              {result.errors.map((e, i) => (
                <Typography key={i} variant="body2" sx={{ fontFamily: 'monospace' }}>
                  {e}
                </Typography>
              ))}
            </Alert>
          )}
        </CardContent>
      </Card>

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

export default DataBackup;
