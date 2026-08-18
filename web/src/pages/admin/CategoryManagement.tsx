import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  TextField,
  Typography,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Stack,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import FolderIcon from '@mui/icons-material/Folder';
import SubdirectoryArrowRightIcon from '@mui/icons-material/SubdirectoryArrowRight';
import { API_BASE_URL } from '../../services/api';

// 只使用抽象、线性的符号，避免把具体实物当作分类含义。
const LINEAR_ICON_OPTIONS = ['⌁', '◌', '△', '□', '◎', '↗', '≋', '⊕'];

interface Section {
  id: number;
  name: string;
  slug: string;
  description: string;
}

interface Category {
  id: number;
  section_id: number;
  parent_id: number | null;
  name: string;
  slug: string;
  icon: string;
  sort_order: number;
  article_count: number;
  child_count: number;
}

const CategoryManagement: React.FC = () => {
  const [sections] = useState<Section[]>([
    { id: 1, name: '项目沉淀', slug: 'project', description: '' },
    { id: 2, name: '研究解读', slug: 'research', description: '' },
  ]);
  
  const [selectedSectionId, setSelectedSectionId] = useState<number>(1);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Dialog states
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'add' | 'edit'>('add');
  const [currentCategory, setCurrentCategory] = useState<Partial<Category>>({});
  const [parentId, setParentId] = useState<number | null>(null);

  useEffect(() => {
    if (selectedSectionId) {
      loadCategories(selectedSectionId);
    }
  }, [selectedSectionId]);

  const loadCategories = async (sectionId: number) => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/admin/sections/${sectionId}/categories`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );
      if (!response.ok) throw new Error('加载分类失败');
      const data = await response.json();
      setCategories(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddCategory = (parentId: number | null = null) => {
    setDialogMode('add');
    setParentId(parentId);
    setCurrentCategory({
      section_id: selectedSectionId,
      parent_id: parentId,
      name: '',
      slug: '',
      icon: LINEAR_ICON_OPTIONS[0],
      sort_order: 0,
    });
    setDialogOpen(true);
  };

  const handleEditCategory = (category: Category) => {
    setDialogMode('edit');
    setCurrentCategory(category);
    setDialogOpen(true);
  };

  const handleSaveCategory = async () => {
    try {
      const url =
        dialogMode === 'add'
          ? `${API_BASE_URL}/api/v1/admin/categories`
          : `${API_BASE_URL}/api/v1/admin/categories/${currentCategory.id}`;

      const method = dialogMode === 'add' ? 'POST' : 'PUT';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(currentCategory),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '保存失败');
      }

      setSuccess(dialogMode === 'add' ? '分类创建成功' : '分类更新成功');
      setDialogOpen(false);
      loadCategories(selectedSectionId);
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteCategory = async (category: Category) => {
    if (
      !window.confirm(
        `确定要删除分类"${category.name}"吗？${
          category.child_count > 0 ? `\n该分类下有 ${category.child_count} 个子分类` : ''
        }${category.article_count > 0 ? `\n该分类下有 ${category.article_count} 篇文章` : ''}`
      )
    ) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/admin/categories/${category.id}`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '删除失败');
      }

      setSuccess('分类删除成功');
      loadCategories(selectedSectionId);
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Generate slug from name
  const generateSlug = (name: string) => {
    return name
      .toLowerCase()
      .replace(/[一-龥]/g, (char) => {
        // Simple pinyin conversion for common characters
        const pinyinMap: { [key: string]: string } = {
          技: 'ji',
          术: 'shu',
          方: 'fang',
          案: 'an',
          项: 'xiang',
          目: 'mu',
          复: 'fu',
          盘: 'pan',
          架: 'jia',
          构: 'gou',
          设: 'she',
          计: 'ji',
          性: 'xing',
          能: 'neng',
          优: 'you',
          化: 'hua',
          最: 'zui',
          佳: 'jia',
          实: 'shi',
          践: 'jian',
        };
        return pinyinMap[char] || '';
      })
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '');
  };

  const parentCategories = categories.filter((c) => !c.parent_id);
  const getChildCategories = (parentId: number) =>
    categories.filter((c) => c.parent_id === parentId);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          分类管理
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      {/* Section Selector */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <FormControl fullWidth>
            <InputLabel>选择板块</InputLabel>
            <Select
              value={selectedSectionId}
              label="选择板块"
              onChange={(e) => setSelectedSectionId(Number(e.target.value))}
            >
              {sections.map((section) => (
                <MenuItem key={section.id} value={section.id}>
                  {section.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <Box sx={{ mt: 2 }}>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => handleAddCategory(null)}
            >
              添加一级分类
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Categories List */}
      <Card>
        <CardContent>
          {loading ? (
            <Typography color="text.secondary">加载中...</Typography>
          ) : (
            <List>
              {parentCategories.map((parent, index) => {
                const children = getChildCategories(parent.id);
                return (
                  <React.Fragment key={parent.id}>
                    {index > 0 && <Divider />}
                    
                    {/* Parent Category */}
                    <ListItem
                      sx={{
                        bgcolor: 'grey.50',
                        borderRadius: 1,
                        mb: 1,
                      }}
                    >
                      <FolderIcon sx={{ mr: 2, color: 'primary.main' }} />
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="h6" sx={{ fontSize: '16px' }}>
                              {parent.icon} {parent.name}
                            </Typography>
                            <Chip label={`${parent.article_count} 篇`} size="small" />
                          </Box>
                        }
                        secondary={`Slug: ${parent.slug}`}
                      />
                      <ListItemSecondaryAction>
                        <Button
                          size="small"
                          startIcon={<AddIcon />}
                          onClick={() => handleAddCategory(parent.id)}
                          sx={{ mr: 1 }}
                        >
                          添加二级分类
                        </Button>
                        <IconButton
                          edge="end"
                          onClick={() => handleEditCategory(parent)}
                          sx={{ mr: 1 }}
                        >
                          <EditIcon />
                        </IconButton>
                        <IconButton
                          edge="end"
                          onClick={() => handleDeleteCategory(parent)}
                          color="error"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>

                    {/* Child Categories */}
                    {children.map((child) => (
                      <ListItem
                        key={child.id}
                        sx={{
                          pl: 6,
                          borderLeft: '2px solid',
                          borderColor: 'grey.200',
                          ml: 2,
                        }}
                      >
                        <SubdirectoryArrowRightIcon sx={{ mr: 2, color: 'grey.500' }} />
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography>
                                {child.icon} {child.name}
                              </Typography>
                              <Chip label={`${child.article_count} 篇`} size="small" variant="outlined" />
                            </Box>
                          }
                          secondary={`Slug: ${child.slug}`}
                        />
                        <ListItemSecondaryAction>
                          <IconButton
                            edge="end"
                            onClick={() => handleEditCategory(child)}
                            sx={{ mr: 1 }}
                          >
                            <EditIcon />
                          </IconButton>
                          <IconButton
                            edge="end"
                            onClick={() => handleDeleteCategory(child)}
                            color="error"
                          >
                            <DeleteIcon />
                          </IconButton>
                        </ListItemSecondaryAction>
                      </ListItem>
                    ))}
                  </React.Fragment>
                );
              })}

              {parentCategories.length === 0 && (
                <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                  暂无分类，点击上方按钮添加
                </Typography>
              )}
            </List>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {dialogMode === 'add' ? '添加分类' : '编辑分类'}
          {parentId && ' (二级分类)'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="分类名称"
              fullWidth
              value={currentCategory.name || ''}
              onChange={(e) => {
                const name = e.target.value;
                setCurrentCategory({
                  ...currentCategory,
                  name,
                  slug: generateSlug(name),
                });
              }}
              required
            />

            <TextField
              label="URL Slug"
              fullWidth
              value={currentCategory.slug || ''}
              onChange={(e) =>
                setCurrentCategory({ ...currentCategory, slug: e.target.value })
              }
              helperText="用于URL路径，建议使用英文字母和连字符"
              required
            />

            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                label="线性图标"
                value={currentCategory.icon || LINEAR_ICON_OPTIONS[0]}
                onChange={(e) =>
                  setCurrentCategory({ ...currentCategory, icon: e.target.value })
                }
                placeholder="⌁"
                sx={{ width: '50%' }}
              />

              <Box sx={{ width: '50%', display: 'flex', flexWrap: 'wrap', gap: 0.75, alignContent: 'center' }}>
                {LINEAR_ICON_OPTIONS.map((icon) => (
                  <Button
                    key={icon}
                    type="button"
                    variant={currentCategory.icon === icon ? 'contained' : 'outlined'}
                    onClick={() => setCurrentCategory({ ...currentCategory, icon })}
                    sx={{
                      minWidth: 34,
                      width: 34,
                      height: 34,
                      p: 0,
                      borderRadius: 1.5,
                      fontSize: 20,
                      lineHeight: 1,
                    }}
                    aria-label={`选择线性图标 ${icon}`}
                  >
                    {icon}
                  </Button>
                ))}
              </Box>

              <TextField
                label="排序顺序"
                type="number"
                value={currentCategory.sort_order || 0}
                onChange={(e) =>
                  setCurrentCategory({
                    ...currentCategory,
                    sort_order: Number(e.target.value),
                  })
                }
                helperText="数字越小越靠前"
                sx={{ width: '50%' }}
              />
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>取消</Button>
          <Button
            onClick={handleSaveCategory}
            variant="contained"
            disabled={!currentCategory.name || !currentCategory.slug}
          >
            保存
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CategoryManagement;
