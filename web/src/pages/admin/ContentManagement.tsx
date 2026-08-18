import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PublishIcon from '@mui/icons-material/Publish';
import UnpublishedIcon from '@mui/icons-material/Unpublished';
import { adminArticleApi, adminSectionApi, adminCategoryApi, mediaUrl } from '../../services/api';

interface Row {
  id: number;
  title: string;
  subtitle?: string;
  status: string;
  section_id: number | null;
  sub_category_id: number | null;
  section_name: string;
  category_name: string;
  banner_url?: string;
  content_type: string;
  created_at: string;
}

const STATUS_LABEL: Record<string, { text: string; color: 'success' | 'default' | 'warning' }> = {
  ready: { text: '已发布', color: 'success' },
  draft: { text: '草稿', color: 'default' },
  pending: { text: '处理中', color: 'warning' },
};

const PAGE_SIZE = 10;

const ContentManagement: React.FC = () => {
  const navigate = useNavigate();
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [sections, setSections] = useState<{ id: number; name: string }[]>([]);
  const [categories, setCategories] = useState<{ id: number; name: string; parent_id: number | null }[]>([]);
  const [sectionId, setSectionId] = useState<number | ''>('');
  const [categoryId, setCategoryId] = useState<number | ''>('');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    adminSectionApi
      .getSections()
      .then((res) => setSections(res.data as any))
      .catch(() => setSections([]));
  }, []);

  useEffect(() => {
    setCategoryId('');
    if (!sectionId) {
      setCategories([]);
      return;
    }
    adminCategoryApi
      .getCategories(Number(sectionId))
      .then((res) => setCategories(res.data as any))
      .catch(() => setCategories([]));
  }, [sectionId]);

  // 排成「一级分类 → 其下二级分类」的顺序，二级缩进显示
  const categoryOptions = useMemo(() => {
    const parents = categories.filter((c) => !c.parent_id);
    const out: { id: number; name: string; level: 0 | 1 }[] = [];
    parents.forEach((p) => {
      out.push({ id: p.id, name: p.name, level: 0 });
      categories
        .filter((c) => c.parent_id === p.id)
        .forEach((child) => out.push({ id: child.id, name: child.name, level: 1 }));
    });
    categories
      .filter((c) => c.parent_id && !parents.some((p) => p.id === c.parent_id))
      .forEach((c) => out.push({ id: c.id, name: c.name, level: 1 }));
    return out;
  }, [categories]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await adminArticleApi.getArticles({
        section_id: sectionId ? Number(sectionId) : undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        status: status || undefined,
        search: search.trim() || undefined,
        page: page + 1,
        limit: PAGE_SIZE,
      });
      const data = res.data as any;
      setRows(data.articles || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载文章列表失败');
    } finally {
      setLoading(false);
    }
  }, [sectionId, categoryId, status, search, page]);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(''), 3000);
  };

  const handleDelete = async (row: Row) => {
    if (!window.confirm(`确定删除文章「${row.title}」？该操作不可撤销。`)) return;
    try {
      await adminArticleApi.deleteArticle(row.id);
      flash('已删除');
      load();
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除失败');
    }
  };

  const handleToggleStatus = async (row: Row) => {
    try {
      if (row.status === 'ready') {
        await adminArticleApi.unpublishArticle(row.id);
        flash('已转为草稿');
      } else {
        await adminArticleApi.publishArticle(row.id);
        flash('已发布');
      }
      load();
    } catch (err: any) {
      setError(err.response?.data?.detail || '操作失败');
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          内容管理
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          component={RouterLink}
          to="/admin/content/new"
        >
          发布内容
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {notice && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice('')}>
          {notice}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <FormControl sx={{ minWidth: 160 }} size="small">
              <InputLabel>板块</InputLabel>
              <Select
                label="板块"
                value={sectionId}
                onChange={(e) => {
                  setPage(0);
                  setSectionId(Number(e.target.value) || '');
                }}
              >
                <MenuItem value="">全部</MenuItem>
                {sections.map((s) => (
                  <MenuItem key={s.id} value={s.id}>
                    {s.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl sx={{ minWidth: 160 }} size="small" disabled={!sectionId}>
              <InputLabel>分类</InputLabel>
              <Select
                label="分类"
                value={categoryId}
                onChange={(e) => {
                  setPage(0);
                  setCategoryId(Number(e.target.value) || '');
                }}
              >
                <MenuItem value="">全部</MenuItem>
                {categoryOptions.map((c) => (
                  <MenuItem
                    key={c.id}
                    value={c.id}
                    sx={c.level === 1 ? { pl: 4 } : { fontWeight: 600 }}
                  >
                    {c.level === 1 ? `— ${c.name}` : c.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl sx={{ minWidth: 140 }} size="small">
              <InputLabel>状态</InputLabel>
              <Select
                label="状态"
                value={status}
                onChange={(e) => {
                  setPage(0);
                  setStatus(e.target.value);
                }}
              >
                <MenuItem value="">全部</MenuItem>
                <MenuItem value="ready">已发布</MenuItem>
                <MenuItem value="draft">草稿</MenuItem>
                <MenuItem value="pending">处理中</MenuItem>
              </Select>
            </FormControl>

            <TextField
              size="small"
              label="搜索标题或摘要"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setPage(0);
                  load();
                }
              }}
              sx={{ flexGrow: 1 }}
            />
          </Stack>
        </CardContent>
      </Card>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>标题</TableCell>
              <TableCell>板块 / 分类</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>创建时间</TableCell>
              <TableCell align="right">操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 5 }}>
                  <CircularProgress size={28} />
                </TableCell>
              </TableRow>
            )}

            {!loading && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 5, color: 'text.secondary' }}>
                  暂无内容，点击右上角「发布内容」开始
                </TableCell>
              </TableRow>
            )}

            {!loading &&
              rows.map((row) => {
                const badge = STATUS_LABEL[row.status] || { text: row.status, color: 'default' as const };
                return (
                  <TableRow key={row.id} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        {row.banner_url && (
                          <Box
                            component="img"
                            src={mediaUrl(row.banner_url)}
                            alt=""
                            sx={{ width: 56, height: 32, objectFit: 'cover', borderRadius: 0.5 }}
                          />
                        )}
                        <Box>
                          <Typography sx={{ fontWeight: 500 }}>{row.title}</Typography>
                          {row.subtitle && (
                            <Typography variant="body2" color="text.secondary">
                              {row.subtitle}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{row.section_name || '—'}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {row.category_name || '未分类'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={badge.text} color={badge.color} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {row.created_at?.slice(0, 10)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title={row.status === 'ready' ? '转为草稿' : '发布'}>
                        <IconButton size="small" onClick={() => handleToggleStatus(row)}>
                          {row.status === 'ready' ? (
                            <UnpublishedIcon fontSize="small" />
                          ) : (
                            <PublishIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="编辑">
                        <IconButton
                          size="small"
                          onClick={() => navigate(`/admin/content/${row.id}/edit`)}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="删除">
                        <IconButton size="small" color="error" onClick={() => handleDelete(row)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>

        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={(_, next) => setPage(next)}
          rowsPerPage={PAGE_SIZE}
          rowsPerPageOptions={[PAGE_SIZE]}
          labelRowsPerPage="每页"
          labelDisplayedRows={({ from, to, count }) => `${from}-${to} / 共 ${count}`}
        />
      </TableContainer>
    </Box>
  );
};

export default ContentManagement;
