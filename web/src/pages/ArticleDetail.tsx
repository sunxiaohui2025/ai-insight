import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Typography,
  Box,
  Paper,
  Chip,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
  Divider,
} from '@mui/material';
import ReactMarkdown from 'react-markdown';
import HtmlPageFrame from '../components/HtmlPageFrame';
import { Article } from '../types';
import { blogApi, mediaUrl } from '../services/api';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import ArticleIcon from '@mui/icons-material/Article';
import DescriptionIcon from '@mui/icons-material/Description';
import * as pdfjsLib from 'pdfjs-dist';
// CRA 将 worker 作为独立资源处理，避免回退到浏览器原生 PDF 阅读器。
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.js';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

type ViewMode = 'full' | 'summary';

const PdfWebReader: React.FC<{ src: string }> = ({ src }) => {
  const pagesRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const renderPdf = async () => {
      try {
        setLoading(true);
        setError(false);
        const pdf = await pdfjsLib.getDocument(src).promise;
        if (cancelled || !pagesRef.current) return;
        pagesRef.current.replaceChildren();

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
          const page = await pdf.getPage(pageNumber);
          if (cancelled || !pagesRef.current) return;
          const baseViewport = page.getViewport({ scale: 1 });
          const maxWidth = Math.min(pagesRef.current.clientWidth || 760, 860);
          const scale = Math.min(maxWidth / baseViewport.width, 1.45);
          const viewport = page.getViewport({ scale });
          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d');
          if (!context) continue;
          const outputScale = window.devicePixelRatio || 1;
          canvas.width = Math.floor(viewport.width * outputScale);
          canvas.height = Math.floor(viewport.height * outputScale);
          canvas.style.width = `${viewport.width}px`;
          canvas.style.height = `${viewport.height}px`;
          canvas.style.maxWidth = '100%';
          canvas.style.display = 'block';
          canvas.style.margin = '0 auto';
          canvas.style.background = '#fff';
          canvas.setAttribute('aria-label', `第 ${pageNumber} 页`);
          pagesRef.current.appendChild(canvas);
          await page.render({
            canvasContext: context,
            viewport,
            transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined,
          }).promise;
        }
      } catch (renderError) {
        console.error('Failed to render PDF:', renderError);
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    renderPdf();
    return () => {
      cancelled = true;
    };
  }, [src]);

  if (error) {
    return <Typography color="text.secondary" sx={{ p: 4, textAlign: 'center' }}>PDF 暂时无法预览，请使用下方链接打开原文件。</Typography>;
  }

  return (
    <Box sx={{ position: 'relative', bgcolor: 'background.paper', minHeight: 220 }}>
      {loading && <Typography color="text.secondary" sx={{ p: 4, textAlign: 'center' }}>正在加载文档…</Typography>}
      <Box ref={pagesRef} sx={{ display: 'grid', gap: 3, bgcolor: 'background.default', py: 2 }} />
    </Box>
  );
};

const ArticleDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('full');

  useEffect(() => {
    if (id) {
      loadArticle(parseInt(id));
    }
  }, [id]);

  const loadArticle = async (articleId: number) => {
    try {
      setLoading(true);
      const response = await blogApi.getArticleById(articleId);
      setArticle(response.data || null);
    } catch (error) {
      console.error('Failed to load article:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: ViewMode | null) => {
    if (newMode !== null) {
      setViewMode(newMode);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', { 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!article) {
    return (
      <Container maxWidth="md" sx={{ py: 6 }}>
        <Typography variant="h5" color="text.secondary" sx={{ textAlign: 'center' }}>
          文章未找到
        </Typography>
      </Container>
    );
  }

  // 正文以 HTML 形式存放在 manual_content 的类型（富文本 / 源码 / 文档转换 / 网页链接提取 / 分享页技能解读）
  const htmlContentTypes = ['manual', 'link', 'document', 'skill'];
  const content = viewMode === 'full'
    ? (htmlContentTypes.includes(article.content_type)
        ? article.manual_content
        : article.translated_content || article.original_content)
    : (article.summary_content || (article as any).one_page_summary || '');

  // 后台发布的 richtext / html / 已转换的文档 / 网页链接，正文本身就是 HTML，需要渲染而不是当 Markdown 处理。
  // 服务端在入库前已做白名单过滤（去掉 script、事件属性、危险 URL），并保留允许的视频嵌入与图片。
  const isHtmlBody =
    viewMode === 'full' &&
    htmlContentTypes.includes(article.content_type) &&
    (article.content_format === 'html' ||
      article.content_format === 'richtext' ||
      article.content_format === 'document' ||
      article.content_format === 'link');
  // html 类型是作者自带样式的整页文档，要在隔离的 iframe 里渲染才能保留原有效果
  const isFullPageHtml =
    isHtmlBody &&
    article.content_format === 'html' &&
    /<(style|!doctype|html|body)\b/i.test(content || '');
  const isPdfBody =
    viewMode === 'full' && article.content_format === 'document' && article.doc_kind === 'pdf';
  // 一页纸解读：正文与一页纸都是 HTML；技能/后台生成的常是带样式的整页，用独立 iframe 还原
  const summary = (article.summary_content || (article as any).one_page_summary || '').trim();
  const summaryFullPage = /<(style|!doctype|html|body)\b/i.test(summary);

  const bodyStyles = {
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    fontSize: '18px',
    '& h1, & h2, & h3, & h4, & h5, & h6': { mt: 3, mb: 2, fontWeight: 600 },
    '& p': { mb: 2, lineHeight: 1.8 },
    '& ul, & ol': { pl: 3, mb: 2 },
    '& li': { mb: 1, lineHeight: 1.8 },
    '& code': {
      bgcolor: 'grey.200',
      px: 1,
      py: 0.5,
      borderRadius: 1,
      fontSize: '0.9em',
    },
    '& pre': {
      bgcolor: 'grey.800',
      color: 'white',
      p: 2,
      borderRadius: 1,
      overflow: 'auto',
      mb: 2,
    },
    '& pre code': { bgcolor: 'transparent', p: 0 },
    '& blockquote': {
      borderLeft: '4px solid',
      borderColor: 'primary.main',
      pl: 2,
      ml: 0,
      fontStyle: 'italic',
      color: 'text.secondary',
    },
    '& img': { maxWidth: '100%', height: 'auto', borderRadius: 1 },
    '& video': { maxWidth: '100%', height: 'auto', display: 'block', borderRadius: 1 },
    '& iframe': { maxWidth: '100%', display: 'block', aspectRatio: '16 / 9', borderRadius: 1 },
    '& figure': { maxWidth: '100%', margin: '24px 0' },
    '& figure img': { display: 'block', margin: '0 auto' },
    '& figcaption': { fontSize: '0.85em', color: 'text.secondary', textAlign: 'center', mt: 1 },
    '& table': { width: '100%', borderCollapse: 'collapse', mb: 2 },
    '& th, & td': { border: '1px solid', borderColor: 'divider', p: 1, textAlign: 'left' },
  } as const;

  return (
    <Container maxWidth="md" sx={{ py: 6 }}>
      {/* Banner */}
      {article.banner_url && (
        <Box
          component="img"
          src={mediaUrl(article.banner_url)}
          alt={`${article.title} 的配图`}
          sx={{
            width: '100%',
            aspectRatio: '2 / 1',
            objectFit: 'cover',
            borderRadius: 2,
            mb: 4,
            display: 'block',
          }}
        />
      )}

      {/* Article Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom sx={{ fontWeight: 600, mb: 1 }}>
          {article.title}
        </Typography>

        {article.subtitle && (
          <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 400, mb: 2 }}>
            {article.subtitle}
          </Typography>
        )}

        {/* 元标签：板块、分类、作者、时间、字数 */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
          {article.section_name && (
            <Chip label={article.section_name} size="small" color="primary" />
          )}
          {article.category_name && (
            <Chip label={article.category_name} size="small" variant="outlined" />
          )}

          {article.author_name && (
            <Typography variant="body2" color="text.secondary">
              {article.author_name}
            </Typography>
          )}

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <AccessTimeIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
            <Typography variant="body2" color="text.secondary">
              {formatDate(article.created_at)}
            </Typography>
          </Box>

          {article.word_count > 0 && (
            <Typography variant="body2" color="text.secondary">
              {article.word_count} 字
            </Typography>
          )}
        </Box>

        {/* View Mode Toggle */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={handleViewModeChange}
            aria-label="view mode"
          >
            <ToggleButton value="full" aria-label="full content">
              <ArticleIcon sx={{ mr: 1 }} />
              正文
            </ToggleButton>
            <ToggleButton value="summary" aria-label="summary" disabled={!summary}>
              <DescriptionIcon sx={{ mr: 1 }} />
              一页纸解读
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        <Divider />
      </Box>

      {/* Article Content */}
      {isPdfBody ? (
        <Box
          sx={{
            bgcolor: 'background.paper',
            borderRadius: 2,
            overflow: 'hidden',
          }}
        >
          <PdfWebReader src={mediaUrl(article.attachment_url)} />
          <Box sx={{ py: 2.5, textAlign: 'center', borderTop: '1px solid', borderColor: 'divider' }}>
            <a
              href={mediaUrl(article.attachment_url)}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#1a73e8', textDecoration: 'none', fontSize: 14 }}
            >
              在新窗口打开 / 下载 {article.attachment_name || '文档'}
            </a>
          </Box>
        </Box>
      ) : isFullPageHtml ? (
        /* 整页 HTML：不加站点的 Paper 外壳，交给作者自己的样式铺满 */
        <Box sx={{ borderRadius: 2, overflow: 'hidden' }}>
          <HtmlPageFrame html={content} title={`${article.title} 正文`} />
        </Box>
      ) : viewMode === 'summary' && summaryFullPage ? (
        /* 一页纸是自带样式的整页，放到隔离 iframe 里还原 */
        <HtmlPageFrame html={summary} title="一页纸解读" />
      ) : (
        <Paper elevation={0} sx={{ pt: 4, pb: 4, px: 0, bgcolor: 'grey.50', borderRadius: 2 }}>
          {viewMode === 'summary' && !summary ? (
            <Typography color="text.secondary" sx={{ textAlign: 'center' }}>
              暂无一页纸解读
            </Typography>
          ) : viewMode === 'summary' && !isHtmlBody ? (
            /* 一页纸也是 HTML，直接渲染（不是 Markdown） */
            <Box sx={bodyStyles} dangerouslySetInnerHTML={{ __html: summary || '<p>暂无内容</p>' }} />
          ) : isHtmlBody ? (
            <Box sx={bodyStyles} dangerouslySetInnerHTML={{ __html: content || '<p>暂无内容</p>' }} />
          ) : (
            <Box sx={bodyStyles}>
              <ReactMarkdown>{content || '暂无内容'}</ReactMarkdown>
            </Box>
          )}
        </Paper>
      )}

      {/* 非 PDF 文档：提供原始文件下载 */}
      {article.content_format === 'document' && article.doc_kind !== 'pdf' && article.attachment_url && (
        <Box sx={{ mt: 3, textAlign: 'center' }}>
          <a
            href={mediaUrl(article.attachment_url)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#1a73e8', textDecoration: 'none', fontSize: 14 }}
          >
            下载原始文档：{article.attachment_name || '文档'}
          </a>
        </Box>
      )}

      {/* Source Link — 后台手写文章的 url 是内部占位符，不展示 */}
      {article.url && /^https?:\/\//i.test(article.url) && (
        <Box sx={{ mt: 4, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            原文链接：
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#1a73e8', textDecoration: 'none' }}
            >
              {article.url}
            </a>
          </Typography>
        </Box>
      )}
    </Container>
  );
};

export default ArticleDetail;
