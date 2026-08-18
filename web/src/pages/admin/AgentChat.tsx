import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  IconButton,
  Chip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Radio,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import RefreshIcon from '@mui/icons-material/Refresh';
import PublishIcon from '@mui/icons-material/Publish';
import MenuBookOutlinedIcon from '@mui/icons-material/MenuBookOutlined';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import FolderOpenOutlinedIcon from '@mui/icons-material/FolderOpenOutlined';
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined';
import { agentApi } from '../../services/api';
import { AgentMessage, AgentSession } from '../../types';
import ReactMarkdown from 'react-markdown';

interface AgentChatProps {
  sessionId: string;
  onPublish?: () => void;
}

const AgentChat: React.FC<AgentChatProps> = ({ sessionId, onPublish }) => {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<any>(null);
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [sectionId, setSectionId] = useState<number>(1);
  const [categoryId, setCategoryId] = useState<number | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadMessages();
    loadDraft();
  }, [sessionId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadMessages = async () => {
    try {
      const response = await agentApi.getMessages(sessionId);
      setMessages(response.data.data || []);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  };

  const loadDraft = async () => {
    try {
      const response = await agentApi.getArticle(sessionId);
      setDraft(response.data.data);
    } catch (error) {
      console.error('Failed to load draft:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || loading) return;

    const userMessage = inputMessage;
    setInputMessage('');
    setLoading(true);

    try {
      const response = await agentApi.sendMessage(sessionId, userMessage);
      await loadMessages();
      if (response.data.data?.draft) {
        setDraft(response.data.data.draft);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(true);
    try {
      await agentApi.uploadFile(sessionId, file);
      await loadMessages();
      await loadDraft();
    } catch (error) {
      console.error('Failed to upload file:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setLoading(true);
    try {
      await agentApi.regenerate(sessionId);
      await loadMessages();
      await loadDraft();
    } catch (error) {
      console.error('Failed to regenerate:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async () => {
    try {
      await agentApi.publish(sessionId, {
        section_id: sectionId,
        category_id: categoryId,
      });
      setPublishDialogOpen(false);
      onPublish?.();
    } catch (error) {
      console.error('Failed to publish:', error);
    }
  };

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 100px)', gap: 2 }}>
      {/* Left: Chat Area */}
      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ p: 2, borderBottom: '1px solid #dadce0' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            AI Agent 对话
          </Typography>
        </Box>

        {/* Messages */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          {messages.map((msg) => (
            <Box
              key={msg.id}
              sx={{
                mb: 2,
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <Paper
                sx={{
                  p: 2,
                  maxWidth: '80%',
                  bgcolor: msg.role === 'user' ? 'primary.main' : 'grey.100',
                  color: msg.role === 'user' ? 'white' : 'text.primary',
                }}
              >
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {msg.content}
                </Typography>
              </Paper>
            </Box>
          ))}
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}
          <div ref={messagesEndRef} />
        </Box>

        {/* Input Area */}
        <Box sx={{ p: 2, borderTop: '1px solid #dadce0', display: 'flex', gap: 1 }}>
          <input
            ref={fileInputRef}
            type="file"
            hidden
            onChange={handleFileUpload}
          />
          <IconButton onClick={() => fileInputRef.current?.click()} disabled={loading}>
            <AttachFileIcon />
          </IconButton>
          <TextField
            fullWidth
            placeholder="输入消息、链接或指令..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
            disabled={loading}
          />
          <IconButton color="primary" onClick={handleSendMessage} disabled={loading || !inputMessage.trim()}>
            <SendIcon />
          </IconButton>
        </Box>
      </Paper>

      {/* Right: Preview Area */}
      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ p: 2, borderBottom: '1px solid #dadce0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            文章预览
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size="small"
              startIcon={<RefreshIcon />}
              onClick={handleRegenerate}
              disabled={loading}
            >
              重新生成
            </Button>
            <Button
              size="small"
              variant="contained"
              startIcon={<PublishIcon />}
              onClick={() => setPublishDialogOpen(true)}
              disabled={!draft?.title}
            >
              发布
            </Button>
          </Box>
        </Box>

        {/* Article Preview */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
          {draft ? (
            <>
              <Typography variant="h4" gutterBottom sx={{ fontWeight: 600 }}>
                {draft.title || '未命名文章'}
              </Typography>
              {draft.excerpt && (
                <Typography variant="body1" color="text.secondary" sx={{ fontStyle: 'italic', mb: 2 }}>
                  {draft.excerpt}
                </Typography>
              )}
              <Box sx={{ my: 2 }}>
                <ReactMarkdown>{draft.content || ''}</ReactMarkdown>
              </Box>
            </>
          ) : (
            <Typography color="text.secondary" sx={{ mt: 4, textAlign: 'center' }}>
              开始对话，Agent 将帮助你生成文章内容
            </Typography>
          )}
        </Box>
      </Paper>

      {/* Publish Dialog */}
      <Dialog open={publishDialogOpen} onClose={() => setPublishDialogOpen(false)}>
        <DialogTitle>发布文章</DialogTitle>
        <DialogContent sx={{ minWidth: 400 }}>
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>板块</InputLabel>
            <Select
              value={sectionId}
              onChange={(e) => setSectionId(e.target.value as number)}
            >
              <MenuItem value={1}>项目沉淀</MenuItem>
              <MenuItem value={2}>研究解读</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>分类（可选）</InputLabel>
            <Select
              value={categoryId || ''}
              onChange={(e) => setCategoryId(e.target.value as number || undefined)}
            >
              <MenuItem value="">无</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPublishDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handlePublish}>
            确认发布
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AgentChat;
