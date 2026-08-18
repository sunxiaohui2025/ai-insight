import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Box } from '@mui/material';

interface Props {
  /** 已在服务端过滤过的完整 HTML 页面（保留作者自己的 <style>） */
  html: string;
  title?: string;
}

/**
 * 在隔离的 iframe 里渲染作者上传的整页 HTML。
 *
 * 用 iframe 而不是 dangerouslySetInnerHTML，是因为整页 HTML 自带 <style>、CSS 变量和
 * 媒体查询：直接内联会被站点样式覆盖，也会反过来污染整站。sandbox 不含 allow-scripts，
 * 所以页面里的脚本不会执行（服务端也已经删掉了 script）；保留 allow-same-origin 只是
 * 为了能读到内容高度做自适应，避免出现内部滚动条。
 */
/**
 * 网页链接 / 后台生成的整页 HTML 自带 .container 的 max-width（~760-780px），
 * 在 900px 的文章容器里居中后，正文会比上面的 banner / 标题窄很多。
 * 这里注入一段样式，把正文主容器撑满 iframe（与 banner 同宽），避免内容过窄。
 */
const WIDTH_FIX_CSS = `
  html, body { width: 100% !important; }
  .container { max-width: none !important; }
`;

const applyWidthFix = (html: string): string => {
  const style = `<style>${WIDTH_FIX_CSS}</style>`;
  const headClose = /<\/head\s*>/i;
  if (headClose.test(html)) {
    return html.replace(headClose, `${style}</head>`);
  }
  const bodyOpen = /<body[^>]*>/i;
  if (bodyOpen.test(html)) {
    return html.replace(bodyOpen, (m) => `${m}${style}`);
  }
  return `${style}${html}`;
};

const HtmlPageFrame: React.FC<Props> = ({ html, title }) => {
  const ref = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(600);

  const measure = useCallback(() => {
    const doc = ref.current?.contentDocument;
    if (!doc?.body) return;
    const next = Math.max(
      doc.body.scrollHeight,
      doc.documentElement?.scrollHeight || 0
    );
    if (next > 0) setHeight(next + 8);
  }, []);

  useEffect(() => {
    // 网络字体和图片加载完成后高度会变，短时间内多测几次即可稳定
    const timers = [120, 400, 1200, 2500].map((delay) => window.setTimeout(measure, delay));
    window.addEventListener('resize', measure);
    return () => {
      timers.forEach(window.clearTimeout);
      window.removeEventListener('resize', measure);
    };
  }, [measure, html]);

  return (
    <Box
      component="iframe"
      ref={ref}
      title={title || '文章内容'}
      srcDoc={applyWidthFix(html)}
      onLoad={measure}
      sandbox="allow-same-origin allow-scripts allow-popups allow-popups-to-escape-sandbox"
      sx={{
        width: '100%',
        height,
        display: 'block',
        border: 0,
        overflow: 'hidden',
        bgcolor: 'transparent',
      }}
    />
  );
};

export default HtmlPageFrame;
