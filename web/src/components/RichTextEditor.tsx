import React, { useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import { Box, ToggleButton, ToggleButtonGroup, Divider } from '@mui/material';
import FormatBoldIcon from '@mui/icons-material/FormatBold';
import FormatItalicIcon from '@mui/icons-material/FormatItalic';
import StrikethroughSIcon from '@mui/icons-material/StrikethroughS';
import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import FormatQuoteIcon from '@mui/icons-material/FormatQuote';
import CodeIcon from '@mui/icons-material/Code';
import LinkIcon from '@mui/icons-material/Link';
import ImageIcon from '@mui/icons-material/Image';
import HorizontalRuleIcon from '@mui/icons-material/HorizontalRule';
import UndoIcon from '@mui/icons-material/Undo';
import RedoIcon from '@mui/icons-material/Redo';

interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  /** 上传图片并返回可访问地址 */
  onUploadImage?: (file: File) => Promise<string>;
  minHeight?: number;
}

const RichTextEditor: React.FC<RichTextEditorProps> = ({
  value,
  onChange,
  onUploadImage,
  minHeight = 360,
}) => {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false, HTMLAttributes: { rel: 'noopener noreferrer' } }),
      Image.configure({ inline: false }),
    ],
    content: value || '',
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  // 外部内容变化时同步（例如 AI 排版优化后回填）
  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    const next = value || '';
    if (next !== current) {
      editor.commands.setContent(next, { emitUpdate: false });
    }
  }, [value, editor]);

  if (!editor) return null;

  const handleInsertLink = () => {
    const previous = editor.getAttributes('link').href as string | undefined;
    const url = window.prompt('输入链接地址', previous || 'https://');
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    if (!/^https?:\/\//i.test(url)) {
      window.alert('请输入以 http:// 或 https:// 开头的地址');
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  };

  const handleInsertImage = async () => {
    if (!onUploadImage) return;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const url = await onUploadImage(file);
        editor.chain().focus().setImage({ src: url }).run();
      } catch (err: any) {
        window.alert(err?.message || '图片上传失败');
      }
    };
    input.click();
  };

  return (
    <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 0.5,
          p: 1,
          bgcolor: 'grey.50',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <ToggleButtonGroup size="small" value={[]}>
          <ToggleButton
            value="bold"
            selected={editor.isActive('bold')}
            onClick={() => editor.chain().focus().toggleBold().run()}
            aria-label="粗体"
          >
            <FormatBoldIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton
            value="italic"
            selected={editor.isActive('italic')}
            onClick={() => editor.chain().focus().toggleItalic().run()}
            aria-label="斜体"
          >
            <FormatItalicIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton
            value="strike"
            selected={editor.isActive('strike')}
            onClick={() => editor.chain().focus().toggleStrike().run()}
            aria-label="删除线"
          >
            <StrikethroughSIcon fontSize="small" />
          </ToggleButton>
        </ToggleButtonGroup>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        <ToggleButtonGroup size="small" value={[]}>
          {[2, 3].map((level) => (
            <ToggleButton
              key={level}
              value={`h${level}`}
              selected={editor.isActive('heading', { level })}
              onClick={() =>
                editor.chain().focus().toggleHeading({ level: level as 2 | 3 }).run()
              }
              aria-label={`标题 ${level}`}
              sx={{ fontWeight: 600, fontSize: 13 }}
            >
              H{level}
            </ToggleButton>
          ))}
          <ToggleButton
            value="bullet"
            selected={editor.isActive('bulletList')}
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            aria-label="无序列表"
          >
            <FormatListBulletedIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton
            value="ordered"
            selected={editor.isActive('orderedList')}
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            aria-label="有序列表"
          >
            <FormatListNumberedIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton
            value="quote"
            selected={editor.isActive('blockquote')}
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            aria-label="引用"
          >
            <FormatQuoteIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton
            value="code"
            selected={editor.isActive('codeBlock')}
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
            aria-label="代码块"
          >
            <CodeIcon fontSize="small" />
          </ToggleButton>
        </ToggleButtonGroup>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        <ToggleButtonGroup size="small" value={[]}>
          <ToggleButton value="link" onClick={handleInsertLink} aria-label="插入链接">
            <LinkIcon fontSize="small" />
          </ToggleButton>
          {onUploadImage && (
            <ToggleButton value="image" onClick={handleInsertImage} aria-label="插入图片">
              <ImageIcon fontSize="small" />
            </ToggleButton>
          )}
          <ToggleButton
            value="hr"
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
            aria-label="分割线"
          >
            <HorizontalRuleIcon fontSize="small" />
          </ToggleButton>
        </ToggleButtonGroup>

        <Box sx={{ flexGrow: 1 }} />

        <ToggleButtonGroup size="small" value={[]}>
          <ToggleButton
            value="undo"
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
            aria-label="撤销"
          >
            <UndoIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton
            value="redo"
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
            aria-label="重做"
          >
            <RedoIcon fontSize="small" />
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <Box
        onClick={() => editor.chain().focus().run()}
        sx={{
          p: 2,
          minHeight,
          // 内容过长时限制高度并在内部滚动，避免把下方的按钮顶出屏幕
          maxHeight: 560,
          overflowY: 'auto',
          cursor: 'text',
          '& .ProseMirror': { outline: 'none', minHeight: minHeight - 32 },
          '& .ProseMirror p': { margin: '0 0 1em' },
          '& .ProseMirror h2': { fontSize: '1.5rem', fontWeight: 600, margin: '1.2em 0 0.6em' },
          '& .ProseMirror h3': { fontSize: '1.2rem', fontWeight: 600, margin: '1em 0 0.5em' },
          '& .ProseMirror blockquote': {
            borderLeft: '3px solid',
            borderColor: 'divider',
            margin: '1em 0',
            paddingLeft: 2,
            color: 'text.secondary',
          },
          '& .ProseMirror pre': {
            bgcolor: 'grey.100',
            p: 1.5,
            borderRadius: 1,
            overflowX: 'auto',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            fontSize: 13,
          },
          '& .ProseMirror img': { maxWidth: '100%', height: 'auto', borderRadius: 4 },
        }}
      >
        <EditorContent editor={editor} />
      </Box>
    </Box>
  );
};

export default RichTextEditor;
