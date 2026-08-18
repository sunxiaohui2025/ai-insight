import React from 'react';
import { Card, CardContent, CardActionArea, Typography, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { Article } from '../types';
import { mediaUrl } from '../services/api';

interface ArticleCardProps {
  article: Article;
}

// 分类色只用于无 banner 时的占位底纹，不再进入正文与元数据
const getCategoryColor = (categoryName?: string) => {
  const colors: Record<string, string> = {
    // 项目沉淀
    '技术方案': '#cf765f',
    '项目复盘': '#0d652d',
    '架构设计': '#1a73e8',
    '性能优化': '#e37400',
    '最佳实践': '#5f6368',
    // 研究解读
    'AI/大模型': '#9334e6',
    '系统架构': '#0f766e',
    '前端技术': '#1a73e8',
    '安全隐私': '#c5221f',
    '行业趋势': '#b45309',
    // 板块兜底
    '研究解读': '#9334e6',
    '项目沉淀': '#cf765f',
  };
  return colors[categoryName || ''] || '#cf765f';
};

const ArticleCard: React.FC<ArticleCardProps> = ({ article }) => {
  const navigate = useNavigate();

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const categoryName = article.category_name || article.section_name || '未分类';
  const tintColor = getCategoryColor(categoryName);
  const hasBanner = Boolean(article.banner_url);

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: 'pointer',
        '--tint': tintColor,
      }}
      onClick={() => navigate(`/article/${article.id}`)}
    >
      {/* Card Cover — 有 banner 时直接展示，否则回退到程序生成的占位封面 */}
      <Box
        sx={{
          position: 'relative',
          aspectRatio: '16/9',
          overflow: 'hidden',
          background: hasBanner
            ? '#f1f3f4'
            : `linear-gradient(150deg, color-mix(in srgb, ${tintColor} 17%, #fff), #fff 75%)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {hasBanner && (
          <Box
            component="img"
            src={mediaUrl(article.banner_url)}
            alt={`${article.title} 的配图`}
            loading="lazy"
            sx={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        )}

        {/* 无 banner 时用点阵作纯装饰占位，不放任何文字或标签 */}
        {!hasBanner && (
          <Box
            aria-hidden="true"
            sx={{
              position: 'absolute',
              inset: 0,
              backgroundImage: `radial-gradient(color-mix(in srgb, ${tintColor} 22%, transparent) 1px, transparent 1px)`,
              backgroundSize: '13px 13px',
              opacity: 0.45,
            }}
          />
        )}
      </Box>

      {/* Card Body */}
      <CardActionArea sx={{ flexGrow: 1 }}>
        <CardContent sx={{ p: '18px 19px 17px', display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
          <Typography
            variant="h6"
            component="h3"
            sx={{
              fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
              fontSize: '19px',
              lineHeight: 1.5,
              fontWeight: 600,
              mb: '10px',
              letterSpacing: '0.01em',
              textWrap: 'pretty',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {article.title}
          </Typography>

          {/* 副标题：优先文章副标题，退回所属板块 */}
          {(article.subtitle || article.section_name) && (
            <Typography
              sx={{
                fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
                fontSize: '15px',
                lineHeight: 1.8,
                letterSpacing: '0.01em',
                color: '#686b68',
                mb: '15px',
                flex: 1,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {article.subtitle || article.section_name}
            </Typography>
          )}

          {/* 无副标题时补一个弹性占位，保证元数据行仍贴在卡片底部 */}
          {!article.subtitle && !article.section_name && <Box sx={{ flex: 1, mb: '15px' }} />}

          {/* Card Footer - 元标签：分类、作者、时间 */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: '8px', mt: 'auto' }}>
            <Box sx={{ display: 'flex', gap: '7px', flexWrap: 'wrap', flex: '1 1 auto', minWidth: 0 }}>
              <Box
                sx={{
                  fontSize: '12.5px',
                  color: '#5f6368',
                  background: '#f1f3f4',
                  border: '1px solid #e3e6e9',
                  borderRadius: '6px',
                  padding: '2px 7px',
                  whiteSpace: 'nowrap',
                }}
              >
                {categoryName}
              </Box>
              {article.author_name && (
                <Box
                  sx={{
                    fontSize: '12.5px',
                    color: '#5f6368',
                    background: '#f1f3f4',
                    border: '1px solid #e3e6e9',
                    borderRadius: '6px',
                    padding: '2px 7px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {article.author_name}
                </Box>
              )}
            </Box>
            <Typography sx={{ fontSize: '12.5px', color: '#5f6368', whiteSpace: 'nowrap', ml: 'auto' }}>
              {formatDate(article.created_at)}
            </Typography>
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
};

export default ArticleCard;
