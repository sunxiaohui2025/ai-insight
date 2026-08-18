import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormHelperText,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import DescriptionIcon from '@mui/icons-material/Description';
import RichTextEditor from '../../components/RichTextEditor';
import HtmlPageFrame from '../../components/HtmlPageFrame';
import {
  publishApi,
  adminSectionApi,
  adminCategoryApi,
  AdminArticlePayload,
  SkillExtractBanner,
  SkillExtractResult,
  SkillExtractLog,
  mediaUrl,
} from '../../services/api';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import ArticleIcon from '@mui/icons-material/Article';
import ImageSearchIcon from '@mui/icons-material/ImageSearch';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

const STEPS = ['编辑内容', '标题与配图', '分类与预览'];

type EditorMode = 'richtext' | 'html' | 'document' | 'link';
type DocKind = 'pdf' | 'docx' | 'markdown' | 'text';

interface DocState {
  url: string;
  name: string;
  kind: DocKind;
  /** 非 PDF 文档在服务端已转成 HTML 正文 */
  html: string;
  /** PDF 前若干页解析出的纯文本，只用来生成标题/副标题/摘要 */
  previewText: string;
  previewPages: number;
  previewNote: string;
}

const TITLE_MIN = 10;
const SUBTITLE_MIN = 50;

/** 中文字数：汉字逐字计，英文/数字按词计（与后端 _cjk_len 一致） */
const cjkLen = (value: string) => {
  const text = (value || '').trim();
  const cjk = text.match(/[一-鿿]/g)?.length || 0;
  const words = text.match(/[A-Za-z0-9]+/g)?.length || 0;
  return cjk + words;
};

const DOC_ACCEPT = '.pdf,.docx,.md,.markdown,.txt';
const DOC_KIND_LABEL: Record<DocKind, string> = {
  pdf: 'PDF',
  docx: 'Word',
  markdown: 'Markdown',
  text: '文本',
};

interface Category {
  id: number;
  name: string;
  parent_id: number | null;
}

const ContentPublish: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);

  const [step, setStep] = useState(0);
  const [mode, setMode] = useState<EditorMode>('richtext');

  const [title, setTitle] = useState('');
  const [subtitle, setSubtitle] = useState('');
  const [contentHtml, setContentHtml] = useState('');
  const [rawHtml, setRawHtml] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [bannerUrl, setBannerUrl] = useState('');
  const [doc, setDoc] = useState<DocState | null>(null);

  // 网页链接提取（由 url-to-article Agent Skill 异步执行）
  const [linkUrl, setLinkUrl] = useState('');
  const [linkContent, setLinkContent] = useState('');
  const [summaryHtml, setSummaryHtml] = useState('');
  const [skillBanners, setSkillBanners] = useState<SkillExtractBanner[]>([]);
  const [skillLogs, setSkillLogs] = useState<SkillExtractLog[]>([]);
  const [bannerDialogOpen, setBannerDialogOpen] = useState(false);
  const skillLogRef = useRef<HTMLDivElement | null>(null);
  const [linkMeta, setLinkMeta] = useState<{
    sourceUrl: string;
    detectedLanguage: string;
    translated: boolean;
    translationModel: string;
  } | null>(null);

  // 步骤三预览：正文 / 一页纸
  const [previewTab, setPreviewTab] = useState<'content' | 'summary'>('content');

  const [sections, setSections] = useState<{ id: number; name: string }[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [sectionId, setSectionId] = useState<number | ''>('');
  const [categoryId, setCategoryId] = useState<number | ''>('');

  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(isEdit);

  // 文档模式下正文来自上传解析结果；PDF 没有 HTML，由前端内嵌阅读器展示
  // 网页链接模式下正文来自提取结果
  const effectiveHtml =
    mode === 'document' ? doc?.html || '' :
    mode === 'link' ? linkContent :
    mode === 'html' ? rawHtml : contentHtml;

  // 自带 <style> / 整页结构的 HTML 要在隔离 iframe 里预览，站点样式否则会覆盖它
  const isFullPageHtml =
    /<style\b/i.test(effectiveHtml) &&
    (mode === 'html' || mode === 'link');

  // 一页纸解读（网站链接技能/编辑时加载的旧文章）
  const effectiveSummaryHtml = summaryHtml;
  const summaryFullPage = /<style\b/i.test(effectiveSummaryHtml || '');

  useEffect(() => {
    adminSectionApi
      .getSections()
      .then((res) => setSections(res.data as any))
      .catch(() => setError('板块加载失败'));
  }, []);

  useEffect(() => {
    if (!sectionId) {
      setCategories([]);
      return;
    }
    adminCategoryApi
      .getCategories(Number(sectionId))
      .then((res) => setCategories(res.data as any))
      .catch(() => setCategories([]));
  }, [sectionId]);

  useEffect(() => {
    if (!isEdit || !id) return;
    publishApi
      .getArticle(Number(id))
      .then((res) => {
        const a = res.data;
        setTitle(a.title || '');
        setSubtitle(a.subtitle || '');
        setContentHtml(a.manual_content || '');
        setRawHtml(a.manual_content || '');
        setExcerpt(a.excerpt || '');
        setSummaryHtml(a.summary_content || a.one_page_summary || '');
        setBannerUrl(a.banner_url || '');
        setSectionId(a.section_id || '');
        setCategoryId(a.sub_category_id || '');
        const format = (a.content_format as EditorMode) || 'richtext';
        setMode(format === 'html' || format === 'document' ? format : 'richtext');
        if (format === 'document' && a.attachment_url) {
          setDoc({
            url: a.attachment_url,
            name: a.attachment_name || '文档',
            kind: (a.doc_kind as DocKind) || 'pdf',
            html: a.manual_content || '',
            // 编辑已有文章时不重新解析 PDF；需要重新提取标题请重新上传
            previewText: '',
            previewPages: 0,
            previewNote: '',
          });
        }
      })
      .catch((err) => setError(err.response?.data?.detail || '文章加载失败'))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(''), 3000);
  };

  const handleUploadImage = useCallback(async (file: File) => {
    const res = await publishApi.uploadImage(file);
    return res.data.url;
  }, []);

  // 技能执行日志更新时，自动滚动到最新一行
  useEffect(() => {
    const el = skillLogRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [skillLogs]);

  const handleExtractUrl = async () => {
    if (!linkUrl.trim()) {
      setError('请输入网页链接');
      return;
    }
    setBusy('extract');
    setError('');
    setSkillLogs([]); // 每次重新提取都清空上一次的执行日志
    try {
      // 1. 交给 url-to-article Agent Skill 异步执行，拿到任务 id
      const run = await publishApi.skillExtract(linkUrl.trim());
      const jobId = run.data.job_id;
      setSkillLogs([{ ts: new Date().toLocaleTimeString(), level: 'info', msg: '任务已提交，等待技能执行…' }]);

      // 2. 轮询直到技能完成；技能会返回正文、一页纸 HTML 和候选 banner
      //    同时把后端实时推送出来的技能执行进度（日志）不断刷新到页面上
      let status = 'running';
      let result: SkillExtractResult | null = null;
      while (status === 'running') {
        await new Promise((r) => setTimeout(r, 1200));
        const poll = await publishApi.skillExtractStatus<SkillExtractResult>(jobId);
        status = poll.data.status;
        // 每次轮询都刷新日志，让用户能看到技能执行的每一步
        if (Array.isArray(poll.data.logs) && poll.data.logs.length > 0) {
          setSkillLogs(poll.data.logs);
        }
        if (poll.data.error) throw new Error(poll.data.error);
        result = poll.data.result;
      }
      // 结束后再拉取一次日志，确保“技能执行完成”这类最后一行也显示出来
      try {
        const finalPoll = await publishApi.skillExtractStatus<SkillExtractResult>(jobId);
        if (Array.isArray(finalPoll.data.logs) && finalPoll.data.logs.length > 0) {
          setSkillLogs(finalPoll.data.logs);
        }
        if (!result && finalPoll.data.result) result = finalPoll.data.result;
      } catch {
        // 忽略结束后的日志拉取错误，不影响主流程
      }
      if (!result) throw new Error('技能未返回结果，请稍后重试');

      setLinkContent(result.content_html);
      setSummaryHtml(result.summary_html || '');
      setSkillBanners(Array.isArray(result.banners) ? result.banners : []);
      setLinkMeta({
        sourceUrl: result.url || linkUrl.trim(),
        detectedLanguage: result.detected_language || '',
        translated: Boolean(result.translated),
        translationModel: '',
      });

      const bannerCount = Array.isArray(result.banners) ? result.banners.length : 0;
      flash(
        `技能提取完成：正文 + 一页纸解读 + ${bannerCount} 张候选 banner${
          result.translated ? '（已翻译为中文）' : ''
        }`
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '提取失败');
    } finally {
      setBusy('');
    }
  };

  const handleModeChange = (next: EditorMode) => {
    if (next === mode) return;
    // 富文本与 HTML 源码共用同一份 HTML，切换时同步；文档模式内容独立
    if (next === 'html') setRawHtml(contentHtml);
    else if (next === 'richtext') setContentHtml(mode === 'html' ? rawHtml : contentHtml);
    setMode(next);
  };

  const handleOptimize = async () => {
    if (!effectiveHtml.trim()) {
      setError('请先填写正文内容');
      return;
    }
    setBusy('optimize');
    setError('');
    try {
      const res = await publishApi.optimizeContent(effectiveHtml, mode);
      setContentHtml(res.data.html);
      setRawHtml(res.data.html);
      if (!excerpt) setExcerpt(res.data.excerpt);
      flash(
        res.data.optimized_by === 'llm'
          ? `${res.data.model} 已重排结构与排版`
          : '未连通配置的大模型，仅做了本地排版规整'
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || '排版优化失败');
    } finally {
      setBusy('');
    }
  };

  const handleExtractMeta = async () => {
    // PDF 正文是二进制，用上传时解析出的前几页文字作为提取依据
    const isPdf = mode === 'document' && doc?.kind === 'pdf';
    const body = isPdf ? doc?.previewText || '' : effectiveHtml;
    // 编辑旧文章时本地没有缓存的 PDF 文字，交给服务端按地址重新解析
    const docUrl = isPdf && !body.trim() ? doc?.url || '' : '';
    if (!body.trim() && !docUrl) {
      setError(
        isPdf
          ? '未能从这份 PDF 中提取到文字（可能是扫描件），请手动填写标题与副标题'
          : '请先在上一步填写正文内容'
      );
      return;
    }
    setBusy('meta');
    setError('');
    try {
      const res = await publishApi.extractMetadata({
        content: body,
        content_format: mode,
        doc_name: doc?.name || '',
        is_plain_text: isPdf,
        doc_url: docUrl,
      });
      setTitle(res.data.title);
      setSubtitle(res.data.subtitle);
      setExcerpt(res.data.excerpt);
      if (res.data.warnings.length) {
        setError(res.data.warnings.join('；'));
      } else {
        flash(
          res.data.source === 'llm'
            ? `已用 ${res.data.model} 提取标题与摘要`
            : '未连通配置的大模型，已按正文本地提取，请检查'
        );
      }

      // 除「网页链接」外的三种模式，提取标题后顺带生成 banner 和一页纸解读：
      // 网页链接由 skill 已产出候选 banner 与一页纸，不需要也不应重复生成。
      if (mode !== 'link') {
        const t = res.data.title.trim();
        const sub = res.data.subtitle.trim();
        const chain: string[] = [];

        if (!bannerUrl && t && sub) {
          try {
            const b = await publishApi.generateBanner({ title: t, subtitle: sub });
            setBannerUrl(b.data.url);
            if (b.data.source === 'llm') chain.push('banner');
          } catch {
            // banner 生成失败不影响标题提取结果
          }
        }
        if (!summaryHtml) {
          try {
            const s = await publishApi.generateSummary({
              content: body,
              content_format: mode,
              title: t,
              is_plain_text: isPdf,
              doc_url: docUrl,
            });
            setSummaryHtml(s.data.html);
            if (s.data.source === 'llm') chain.push('一页纸解读');
          } catch {
            // 一页纸生成失败不影响标题提取结果
          }
        }
        if (chain.length) {
          flash(`已自动生成${chain.join('与')}，可在下方预览/调整`);
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '提取失败');
    } finally {
      setBusy('');
    }
  };

  const handleGenerateSummary = async () => {
    const isPdf = mode === 'document' && doc?.kind === 'pdf';
    const body = isPdf ? doc?.previewText || '' : effectiveHtml;
    const docUrl = isPdf && !body.trim() ? doc?.url || '' : '';
    if (!body.trim() && !docUrl) {
      setError('没有可生成摘要的正文内容，请先在上一步填好正文或上传文档');
      return;
    }
    setBusy('summary');
    setError('');
    try {
      const res = await publishApi.generateSummary({
        content: body,
        content_format: mode,
        title: title.trim(),
        is_plain_text: isPdf,
        doc_url: docUrl,
      });
      setSummaryHtml(res.data.html);
      flash(
        res.data.source === 'llm'
          ? `已用 ${res.data.model} 生成一页纸解读`
          : '未连通配置的大模型，已生成本地默认解读，可手动调整'
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || '一页纸解读生成失败');
    } finally {
      setBusy('');
    }
  };

  const handleGenerateBanner = async () => {
    if (titleShort || subtitleShort) {
      setError('请先补齐标题与副标题，banner 会结合两者内容生成');
      return;
    }
    setBusy('banner');
    setError('');
    try {
      const res = await publishApi.generateBanner({ title: title.trim(), subtitle: subtitle.trim() });
      setBannerUrl(res.data.url);
      flash(
        res.data.source === 'llm'
          ? `${res.data.model} 已生成 banner${res.data.concept ? `：${res.data.concept}` : ''}`
          : '未连通配置的大模型，已生成默认样式 banner'
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Banner 生成失败');
    } finally {
      setBusy('');
    }
  };

  const handleUploadBanner = async (file: File) => {
    setBusy('banner');
    setError('');
    try {
      const res = await publishApi.uploadImage(file);
      setBannerUrl(res.data.url);
      flash('Banner 已上传');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Banner 上传失败');
    } finally {
      setBusy('');
    }
  };

  const handleUploadDoc = async (file: File) => {
    setBusy('doc');
    setError('');
    try {
      const res = await publishApi.uploadDocument(file);
      setDoc({
        url: res.data.url,
        name: res.data.filename,
        kind: res.data.doc_kind,
        html: res.data.html || '',
        previewText: res.data.preview_text || '',
        previewPages: res.data.preview_pages || 0,
        previewNote: res.data.preview_note || '',
      });
      if (res.data.preview_note) {
        setError(res.data.preview_note);
      } else {
        flash(
          res.data.doc_kind === 'pdf'
            ? `PDF 已上传，前端将内嵌在线阅读；已读取前 ${res.data.preview_pages} 页文字用于生成标题`
            : `${DOC_KIND_LABEL[res.data.doc_kind]} 已解析为正文`
        );
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '文档上传失败');
    } finally {
      setBusy('');
    }
  };

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
    // 兜底：父分类缺失的孤儿二级分类也要能选到
    categories
      .filter((c) => c.parent_id && !parents.some((p) => p.id === c.parent_id))
      .forEach((c) => out.push({ id: c.id, name: c.name, level: 1 }));
    return out;
  }, [categories]);

  const titleLen = cjkLen(title);
  const subtitleLen = cjkLen(subtitle);
  const titleShort = titleLen < TITLE_MIN;
  const subtitleShort = subtitleLen < SUBTITLE_MIN;

  const validation = useMemo(() => {
    if (!title.trim()) return '请填写文章标题';
    if (titleLen < TITLE_MIN) return `标题不少于 ${TITLE_MIN} 字，当前 ${titleLen} 字`;
    if (subtitleLen < SUBTITLE_MIN) return `副标题不少于 ${SUBTITLE_MIN} 字，当前 ${subtitleLen} 字`;
    if (mode === 'document') {
      if (!doc) return '请上传文档文件';
      if (doc.kind !== 'pdf' && !doc.html.trim()) return '文档解析结果为空，请检查文件';
    } else if (!effectiveHtml.trim()) {
      return '请填写正文内容';
    }
    if (!sectionId) return '请选择发布板块';
    return '';
  }, [title, titleLen, subtitleLen, mode, doc, effectiveHtml, sectionId]);

  const submit = async (status: 'draft' | 'ready') => {
    if (validation) {
      setError(validation);
      return;
    }
    setBusy(status);
    setError('');
    // 技能提取的网页链接正文是自带头样式/script 的整页 HTML，须以整页模式（html）入库，
    // 阅读端在隔离 sandbox iframe 里还原，语义仍是 link（用于展示原文链接 / 区分来源）。
    const isLink = mode === 'link';
    const payload: AdminArticlePayload = {
      title: title.trim(),
      subtitle: subtitle.trim(),
      section_id: Number(sectionId),
      sub_category_id: categoryId ? Number(categoryId) : null,
      content_html: effectiveHtml,
      content_format: isLink ? 'html' : mode,
      content_type: isLink ? 'link' : undefined,
      excerpt: excerpt.trim(),
      summary_html: effectiveSummaryHtml,
      banner_url: bannerUrl,
      attachment_url: mode === 'document' ? doc?.url || '' : '',
      attachment_name: mode === 'document' ? doc?.name || '' : '',
      doc_kind: mode === 'document' ? doc?.kind || '' : '',
      source_url: isLink ? linkMeta?.sourceUrl || linkUrl.trim() : '',
      status,
    };
    try {
      if (isEdit && id) await publishApi.updateArticle(Number(id), payload);
      else await publishApi.createArticle(payload);
      navigate('/admin/content');
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存失败');
    } finally {
      setBusy('');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <IconButton onClick={() => navigate('/admin/content')} aria-label="返回列表">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          {isEdit ? '编辑内容' : '发布内容'}
        </Typography>
      </Box>

      {step === 1 && !title && !subtitle && !busy && (
        <Alert severity="info" sx={{ mb: 2 }}>
          点击「AI 提取标题与摘要」，将由模型管理里配置的大模型从正文中总结生成。
        </Alert>
      )}

      <Stepper activeStep={step} sx={{ mb: 3 }}>
        {STEPS.map((label, index) => (
          <Step key={label} completed={step > index}>
            <StepLabel sx={{ cursor: 'pointer' }} onClick={() => setStep(index)}>
              {label}
            </StepLabel>
          </Step>
        ))}
      </Stepper>

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

      {/* Step 1 — 编辑内容 */}
      {step === 0 && (
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Tabs value={mode} onChange={(_, v) => handleModeChange(v)}>
                <Tab value="richtext" label="富文本" />
                <Tab value="html" label="HTML 源码" />
                <Tab value="document" label="文档" />
                <Tab value="link" label="网页链接" />
              </Tabs>
              {/* 整页 HTML 自带排版，跑排版优化会丢掉作者的 CSS，所以不提供该按钮 */}
              {mode !== 'document' && mode !== 'link' && !isFullPageHtml && (
                <Button
                  startIcon={busy === 'optimize' ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
                  onClick={handleOptimize}
                  disabled={Boolean(busy)}
                  variant="outlined"
                >
                  {busy === 'optimize' ? 'AI 润色中…' : 'AI 润色排版'}
                </Button>
              )}
            </Box>

            {mode === 'richtext' && (
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  点击右上角「AI 润色排版」，会把这段富文本润色成带配色与层次感的 HTML，
                  发布时保存的是润色后的 HTML，而不是原始文字，阅读页效果会更好。
                </Typography>
                <RichTextEditor
                  value={contentHtml}
                  onChange={setContentHtml}
                  onUploadImage={handleUploadImage}
                />
              </Box>
            )}

            {mode === 'html' && (
              <TextField
                fullWidth
                multiline
                minRows={16}
                maxRows={28}
                label="HTML 源码"
                value={rawHtml}
                onChange={(e) => setRawHtml(e.target.value)}
                placeholder="<h2>小节标题</h2><p>正文…</p>"
                helperText="前端阅读页会渲染这段 HTML，而不是显示源码"
                sx={{
                  '& textarea': {
                    fontFamily: 'ui-monospace, Menlo, monospace',
                    fontSize: 13,
                    maxHeight: '58vh',
                    overflowY: 'auto',
                  },
                }}
              />
            )}

            {mode === 'document' && (
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  上传 PDF / Word(.docx) / Markdown / txt 作为文章正文。PDF 在前端内嵌阅读器里直接翻页阅读，
                  同时会解析前 10 页文字用于下一步生成标题、副标题和 banner；其他格式会转换成正文排版。
                </Typography>

                {doc ? (
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <Chip
                        icon={doc.kind === 'pdf' ? <PictureAsPdfIcon /> : <DescriptionIcon />}
                        label={`${DOC_KIND_LABEL[doc.kind]} · ${doc.name}`}
                        component="a"
                        href={mediaUrl(doc.url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        clickable
                      />
                      <Button component="label" size="small" disabled={Boolean(busy)}>
                        替换文档
                        <input
                          type="file"
                          accept={DOC_ACCEPT}
                          hidden
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleUploadDoc(file);
                            e.target.value = '';
                          }}
                        />
                      </Button>
                      <IconButton size="small" onClick={() => setDoc(null)} aria-label="移除文档">
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Box>

                    {doc.kind === 'pdf' ? (
                      <Box
                        component="iframe"
                        src={mediaUrl(doc.url)}
                        title={`${doc.name} 预览`}
                        sx={{ width: '100%', height: 520, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
                      />
                    ) : (
                      <Box
                        sx={{
                          maxHeight: 520,
                          overflowY: 'auto',
                          p: 2,
                          border: '1px solid',
                          borderColor: 'divider',
                          borderRadius: 1,
                          '& img': { maxWidth: '100%' },
                        }}
                        dangerouslySetInnerHTML={{ __html: doc.html || '<p>（解析结果为空）</p>' }}
                      />
                    )}
                  </Box>
                ) : (
                  <Button
                    component="label"
                    variant="outlined"
                    startIcon={busy === 'doc' ? <CircularProgress size={16} /> : <UploadFileIcon />}
                    disabled={Boolean(busy)}
                  >
                    上传文档
                    <input
                      type="file"
                      accept={DOC_ACCEPT}
                      hidden
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadDoc(file);
                        e.target.value = '';
                      }}
                    />
                  </Button>
                )}
              </Box>
            )}

            {mode === 'link' && (
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  粘贴任意网页链接，交给「url-to-article」Agent Skill 提取。技能会产出一篇幅 HTML 正文、
                  一页纸解读，以及 1~2 张候选 banner 图；英文文章会自动翻译成中文。
                </Typography>

                <TextField
                  fullWidth
                  label="网页链接"
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="https://example.com/article"
                  sx={{ mb: 2 }}
                />

                <Button
                  variant="contained"
                  startIcon={busy === 'extract' ? <CircularProgress size={16} color="inherit" /> : <AutoFixHighIcon />}
                  onClick={handleExtractUrl}
                  disabled={Boolean(busy) || !linkUrl.trim()}
                  sx={{ mb: 2 }}
                >
                  {busy === 'extract' ? '技能提取中…' : '技能提取'}
                </Button>

                {/* 技能执行过程日志：把 url-to-article 的每一步执行进度实时打印出来 */}
                {(busy === 'extract' || skillLogs.length > 0) && (
                  <Box
                    sx={{
                      mt: 1,
                      mb: 2,
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                      overflow: 'hidden',
                      bgcolor: 'grey.900',
                    }}
                  >
                    <Box
                      sx={{
                        px: 2,
                        py: 1,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        bgcolor: 'grey.800',
                        color: 'grey.200',
                      }}
                    >
                      <AutoAwesomeIcon sx={{ fontSize: 18 }} />
                      <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }}>
                        技能执行日志
                      </Typography>
                      {busy === 'extract' && (
                        <CircularProgress size={14} color="inherit" sx={{ color: 'grey.300' }} />
                      )}
                    </Box>
                    <Box
                      ref={skillLogRef}
                      sx={{
                        px: 2,
                        py: 1,
                        maxHeight: 260,
                        overflowY: 'auto',
                        fontFamily: 'Menlo, Monaco, Consolas, monospace',
                        fontSize: 12,
                        lineHeight: 1.7,
                      }}
                    >
                      {skillLogs.length === 0 ? (
                        <Box sx={{ color: 'grey.400' }}>正在等待技能输出…</Box>
                      ) : (
                        skillLogs.map((log, i) => (
                          <Box
                            key={i}
                            sx={{
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              color:
                                log.level === 'error'
                                  ? 'error.light'
                                  : log.level === 'success'
                                  ? 'success.light'
                                  : 'grey.300',
                            }}
                          >
                            <Box component="span" sx={{ color: 'grey.500', mr: 1 }}>
                              {log.ts}
                            </Box>
                            {log.msg}
                          </Box>
                        ))
                      )}
                    </Box>
                  </Box>
                )}

                {linkContent && (
                  <Box sx={{ mt: 2 }}>
                    {linkMeta && (
                      <Alert severity="info" sx={{ mb: 2 }}>
                        {linkMeta.translated
                          ? `已从英文翻译为中文（检测语言：${linkMeta.detectedLanguage || '英文'}）`
                          : `已提取内容（检测语言：${linkMeta.detectedLanguage === 'zh' ? '中文' : '其他'}）`}
                        {skillBanners.length > 0 && `；已生成 ${skillBanners.length} 张候选 banner，下一步可选用`}
                      </Alert>
                    )}
                    <Box
                      sx={{
                        maxHeight: 520,
                        overflowY: 'auto',
                        p: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 1,
                        bgcolor: 'grey.50',
                        '& img': { maxWidth: '100%', height: 'auto' },
                        '& video': { maxWidth: '100%', height: 'auto', display: 'block', my: 1 },
                        '& iframe': { maxWidth: '100%', display: 'block', aspectRatio: '16 / 9' },
                        '& h1, & h2, & h3': { mt: 2, mb: 1 },
                        '& p': { mb: 1.5, lineHeight: 1.8 },
                      }}
                      dangerouslySetInnerHTML={{ __html: linkContent }}
                    />
                  </Box>
                )}
              </Box>
            )}

            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="contained" onClick={() => setStep(1)}>
                下一步
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Step 2 — 标题与配图 */}
      {step === 1 && (
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  标题与摘要
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  用模型管理里配置的大模型从正文提取。标题不少于 {TITLE_MIN} 字，副标题不少于 {SUBTITLE_MIN} 字。
                  {mode === 'document' && doc?.kind === 'pdf' &&
                    ` PDF 会读取前 ${doc.previewPages || 10} 页文字作为提取依据。`}
                </Typography>
              </Box>
              <Button
                variant="contained"
                startIcon={busy === 'meta' ? <CircularProgress size={16} color="inherit" /> : <AutoFixHighIcon />}
                onClick={handleExtractMeta}
                disabled={Boolean(busy)}
              >
                {busy === 'meta' ? '提取中…' : 'AI 提取标题与摘要'}
              </Button>
            </Box>

            <Stack spacing={2}>
              <TextField
                label="文章标题"
                fullWidth
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                error={Boolean(title) && titleShort}
                helperText={`${titleLen} / 至少 ${TITLE_MIN} 字`}
              />
              <TextField
                label="副标题"
                fullWidth
                required
                multiline
                minRows={2}
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                error={Boolean(subtitle) && subtitleShort}
                helperText={`${subtitleLen} / 至少 ${SUBTITLE_MIN} 字。展示在标题下方，也是生成 banner 的依据`}
              />
              <TextField
                label="摘要"
                fullWidth
                multiline
                minRows={3}
                value={excerpt}
                onChange={(e) => setExcerpt(e.target.value)}
                helperText="展示在列表卡片上。留空则自动取正文前 200 字"
              />
            </Stack>

            <Divider sx={{ my: 3 }} />

            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
              文章 Banner
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              可以上传图片，也可以用配置的大模型按 Anthropic 编辑插画风格生成——会先把主副标题提炼成一个视觉隐喻，
              再据此绘制 SVG。
            </Typography>

            <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
              <Button
                component="label"
                variant="outlined"
                startIcon={<UploadFileIcon />}
                disabled={Boolean(busy)}
              >
                上传图片
                <input
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleUploadBanner(file);
                    e.target.value = '';
                  }}
                />
              </Button>
              <Button
                variant="outlined"
                startIcon={busy === 'banner' ? <CircularProgress size={16} /> : <AutoFixHighIcon />}
                onClick={handleGenerateBanner}
                disabled={Boolean(busy) || titleShort || subtitleShort}
                title={titleShort || subtitleShort ? '需要先补齐标题与副标题' : undefined}
              >
                {busy === 'banner' ? '生成中…' : 'AI 生成 Banner'}
              </Button>
              {skillBanners.length > 0 && (
                <Button
                  variant="outlined"
                  color="secondary"
                  startIcon={<ImageSearchIcon />}
                  onClick={() => setBannerDialogOpen(true)}
                  disabled={Boolean(busy)}
                >
                  选择技能 Banner（{skillBanners.length}）
                </Button>
              )}
              {bannerUrl && (
                <Button color="error" startIcon={<DeleteOutlineIcon />} onClick={() => setBannerUrl('')}>
                  移除
                </Button>
              )}
            </Stack>

            {bannerUrl ? (
              <Box
                component="img"
                src={mediaUrl(bannerUrl)}
                alt={`${title} 的配图`}
                sx={{
                  width: '100%',
                  maxWidth: 720,
                  aspectRatio: '2 / 1',
                  objectFit: 'cover',
                  borderRadius: 1,
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              />
            ) : (
              <Box
                sx={{
                  width: '100%',
                  maxWidth: 720,
                  aspectRatio: '2 / 1',
                  display: 'grid',
                  placeItems: 'center',
                  bgcolor: 'grey.100',
                  borderRadius: 1,
                  color: 'text.secondary',
                }}
              >
                还没有 Banner
              </Box>
            )}

            <Divider sx={{ my: 3 }} />

            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
              一页纸解读
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {mode === 'link'
                ? '已由「网页链接」技能生成，可在此微调；发布后作为文章的一页纸解读展示在正文旁。'
                : '用配置的大模型从正文生成一篇概要解读（HTML），随文章一起发布；点击「AI 提取标题与摘要」也会自动生成。'}
            </Typography>

            <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
              {mode !== 'link' && (
                <Button
                  variant="outlined"
                  startIcon={busy === 'summary' ? <CircularProgress size={16} /> : <AutoFixHighIcon />}
                  onClick={handleGenerateSummary}
                  disabled={Boolean(busy)}
                  title="从正文生成概要解读"
                >
                  {busy === 'summary' ? '生成中…' : 'AI 生成一页纸解读'}
                </Button>
              )}
              {summaryHtml && (
                <Button color="error" startIcon={<DeleteOutlineIcon />} onClick={() => setSummaryHtml('')}>
                  移除
                </Button>
              )}
            </Stack>

            <TextField
              label="一页纸解读（HTML）"
              fullWidth
              multiline
              minRows={6}
              maxRows={20}
              value={summaryHtml}
              onChange={(e) => setSummaryHtml(e.target.value)}
              sx={{
                '& textarea': { fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 13, maxHeight: '55vh', overflowY: 'auto' },
              }}
              helperText="发布后作为文章的一页纸解读展示，可自由编辑这段 HTML。"
            />

            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Button onClick={() => setStep(0)}>上一步</Button>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                {(titleShort || subtitleShort) && (
                  <Typography variant="body2" color="error">
                    {titleShort ? `标题还差 ${TITLE_MIN - titleLen} 字` : `副标题还差 ${SUBTITLE_MIN - subtitleLen} 字`}
                  </Typography>
                )}
                <Button
                  variant="contained"
                  onClick={() => setStep(2)}
                  disabled={titleShort || subtitleShort}
                >
                  下一步
                </Button>
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* 选择技能提取生成的 Banner */}
      <Dialog open={bannerDialogOpen} onClose={() => setBannerDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>选择 Banner 配图</DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            下面是由「url-to-article」技能从这篇文章提取/生成的候选配图，选择一张作为文章 Banner。
          </Typography>
          <Stack spacing={3}>
            {skillBanners.map((b) => {
              const selected = bannerUrl === b.url;
              return (
                <Box
                  key={b.name}
                  onClick={() => setBannerUrl(b.url)}
                  sx={{
                    position: 'relative',
                    border: selected ? '3px solid' : '1px solid',
                    borderColor: selected ? 'primary.main' : 'divider',
                    borderRadius: 2,
                    overflow: 'hidden',
                    cursor: 'pointer',
                  }}
                >
                  <Box
                    component="img"
                    src={mediaUrl(b.url)}
                    alt={b.name}
                    sx={{ width: '100%', maxHeight: 360, objectFit: 'cover', display: 'block' }}
                  />
                  {selected && (
                    <CheckCircleIcon
                      sx={{
                        position: 'absolute', top: 10, right: 10, fontSize: 30,
                        color: 'primary.main', bgcolor: 'background.paper', borderRadius: '50%',
                      }}
                    />
                  )}
                </Box>
              );
            })}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBannerDialogOpen(false)}>取消</Button>
          <Button
            variant="contained"
            onClick={() => setBannerDialogOpen(false)}
            disabled={!bannerUrl}
          >
            使用这张 Banner
          </Button>
        </DialogActions>
      </Dialog>

      {/* Step 3 — 分类与预览 */}
      {step === 2 && (
        <Stack spacing={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                发布分类
              </Typography>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <FormControl fullWidth required>
                  <InputLabel>板块</InputLabel>
                  <Select
                    label="板块"
                    value={sectionId}
                    onChange={(e) => {
                      setSectionId(Number(e.target.value) || '');
                      setCategoryId('');
                    }}
                  >
                    {sections.map((s) => (
                      <MenuItem key={s.id} value={s.id}>
                        {s.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl fullWidth disabled={!sectionId}>
                  <InputLabel>分类</InputLabel>
                  <Select
                    label="分类"
                    value={categoryId}
                    onChange={(e) => setCategoryId(Number(e.target.value) || '')}
                  >
                    <MenuItem value="">不指定</MenuItem>
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
                  {sectionId && categoryOptions.length === 0 && (
                    <FormHelperText>该板块下还没有分类，可先到分类管理里添加</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                发布预览
              </Typography>

              {bannerUrl && (
                <Box
                  component="img"
                  src={mediaUrl(bannerUrl)}
                  alt={`${title} 的配图`}
                  sx={{
                    width: '100%',
                    aspectRatio: '2 / 1',
                    objectFit: 'cover',
                    borderRadius: 1,
                    mb: 3,
                  }}
                />
              )}

              <Typography variant="h4" sx={{ fontWeight: 700 }}>
                {title || '（未填写标题）'}
              </Typography>
              {subtitle && (
                <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 400, mt: 1 }}>
                  {subtitle}
                </Typography>
              )}

              <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                {sectionId && (
                  <Chip size="small" label={sections.find((s) => s.id === Number(sectionId))?.name} />
                )}
                {categoryId && (
                  <Chip
                    size="small"
                    variant="outlined"
                    label={categories.find((c) => c.id === Number(categoryId))?.name}
                  />
                )}
              </Stack>

              <Divider sx={{ my: 3 }} />

              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
                <ToggleButtonGroup
                  value={previewTab}
                  exclusive
                  onChange={(_, v) => { if (v) setPreviewTab(v); }}
                  aria-label="发布预览模式"
                >
                  <ToggleButton value="content" disabled={mode === 'document' && doc?.kind === 'pdf'}>
                    <ArticleIcon sx={{ mr: 1 }} /> 正文
                  </ToggleButton>
                  <ToggleButton value="summary" disabled={!effectiveSummaryHtml}>
                    <DescriptionIcon sx={{ mr: 1 }} /> 一页纸解读
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>

              {previewTab === 'summary' ? (
                effectiveSummaryHtml ? (
                  summaryFullPage ? (
                    <HtmlPageFrame html={effectiveSummaryHtml} title="一页纸解读预览" />
                  ) : (
                    <Box
                      sx={{
                        '& h2': { fontSize: '1.5rem', fontWeight: 600, mt: 4, mb: 1.5 },
                        '& p': { lineHeight: 1.9, mb: 2 },
                        '& img': { maxWidth: '100%', height: 'auto', borderRadius: 1 },
                      }}
                      dangerouslySetInnerHTML={{ __html: effectiveSummaryHtml }}
                    />
                  )
                ) : (
                  <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    暂无一页纸解读
                  </Typography>
                )
              ) : mode === 'document' && doc?.kind === 'pdf' ? (
                <Box>
                  <Box
                    component="iframe"
                    src={mediaUrl(doc.url)}
                    title={`${doc.name} 预览`}
                    sx={{
                      width: '100%',
                      height: 600,
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                    }}
                  />
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    前端阅读页会以同样的内嵌阅读器展示这份 PDF。
                  </Typography>
                </Box>
              ) : isFullPageHtml ? (
                <Box>
                  <HtmlPageFrame html={effectiveHtml} title="正文预览" />
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    这是自带样式的整页 HTML，前端阅读页会保留你的 CSS 原样展示。
                  </Typography>
                </Box>
              ) : (
              <Box
                sx={{
                  '& h2': { fontSize: '1.5rem', fontWeight: 600, mt: 4, mb: 1.5 },
                  '& h3': { fontSize: '1.2rem', fontWeight: 600, mt: 3, mb: 1 },
                  '& p': { lineHeight: 1.9, mb: 2 },
                  '& img': { maxWidth: '100%', height: 'auto', borderRadius: 1 },
                  '& video': { maxWidth: '100%', height: 'auto', display: 'block', my: 1 },
                  '& iframe': { maxWidth: '100%', display: 'block', aspectRatio: '16 / 9' },
                  '& blockquote': {
                    borderLeft: '3px solid',
                    borderColor: 'divider',
                    pl: 2,
                    ml: 0,
                    color: 'text.secondary',
                  },
                  '& pre': { bgcolor: 'grey.100', p: 2, borderRadius: 1, overflowX: 'auto' },
                }}
                dangerouslySetInnerHTML={{ __html: effectiveHtml || '<p>（无正文）</p>' }}
              />
              )}

              {mode === 'document' && doc && doc.kind !== 'pdf' && (
                <Chip
                  sx={{ mt: 2 }}
                  icon={<DescriptionIcon />}
                  label={`原始文档：${doc.name}`}
                  component="a"
                  href={mediaUrl(doc.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  clickable
                />
              )}
            </CardContent>
          </Card>

          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button onClick={() => setStep(1)}>上一步</Button>
            <Stack direction="row" spacing={2}>
              <Button
                variant="outlined"
                onClick={() => submit('draft')}
                disabled={Boolean(busy)}
              >
                存为草稿
              </Button>
              <Button
                variant="contained"
                onClick={() => submit('ready')}
                disabled={Boolean(busy) || Boolean(validation)}
              >
                {busy === 'ready' ? '发布中…' : '确认发布'}
              </Button>
            </Stack>
          </Box>

          {validation && (
            <Typography variant="body2" color="error" sx={{ textAlign: 'right' }}>
              {validation}
            </Typography>
          )}
        </Stack>
      )}
    </Box>
  );
};

export default ContentPublish;
