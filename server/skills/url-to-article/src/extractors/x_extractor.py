"""X (Twitter) 内容提取器"""
from bs4 import BeautifulSoup
import re
from typing import Dict, List
import langdetect


class XExtractor:
    def extract(self, html: str, url: str) -> Dict:
        """
        从 X 页面 HTML 中提取内容
        
        Args:
            html: 页面 HTML
            url: 原始 URL
            
        Returns:
            dict: 提取的内容
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # 提取推文内容
        tweets = self._extract_tweets(soup)
        
        # 提取元数据
        metadata = self._extract_metadata(soup, url)
        
        # 提取媒体资源
        media = self._extract_media(soup)
        
        # 合并所有推文文本
        full_text = "\n\n".join([t["text"] for t in tweets if t["text"]])
        
        # 检测语言
        try:
            language = langdetect.detect(full_text) if full_text else "unknown"
        except:
            language = "unknown"
        
        return {
            "tweets": tweets,
            "full_text": full_text,
            "metadata": metadata,
            "media": media,
            "language": language,
            "is_thread": len(tweets) > 1
        }
    
    def _extract_tweets(self, soup: BeautifulSoup) -> List[Dict]:
        """提取推文内容"""
        tweets = []
        
        # 查找推文文本
        # X 的结构可能变化，这里使用多种选择器
        selectors = [
            'article[data-testid="tweet"]',
            'div[data-testid="tweetText"]',
            'div[lang]'
        ]
        
        # 尝试找到推文容器
        tweet_elements = soup.select('article[data-testid="tweet"]')
        
        if tweet_elements:
            for idx, article in enumerate(tweet_elements):
                # 提取文本
                text_elem = article.select_one('div[data-testid="tweetText"]')
                text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""
                
                # 提取图片
                images = []
                img_elements = article.select('img[src*="media"]')
                for img in img_elements:
                    src = img.get('src', '')
                    if 'media' in src and src not in images:
                        images.append(src)
                
                # 提取视频
                videos = []
                video_elements = article.select('video')
                for video in video_elements:
                    src = video.get('src', '') or video.get('poster', '')
                    if src and src not in videos:
                        videos.append(src)
                
                if text or images or videos:
                    tweets.append({
                        "order": idx + 1,
                        "text": text,
                        "images": images,
                        "videos": videos
                    })
        
        # 如果没找到，尝试备用方案
        if not tweets:
            text_elements = soup.select('div[data-testid="tweetText"]')
            for idx, elem in enumerate(text_elements):
                text = elem.get_text(separator="\n", strip=True)
                if text:
                    tweets.append({
                        "order": idx + 1,
                        "text": text,
                        "images": [],
                        "videos": []
                    })
        
        return tweets
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """提取元数据"""
        metadata = {
            "url": url,
            "author": "",
            "author_handle": "",
            "created_at": "",
            "title": ""
        }
        
        # 提取作者
        author_elem = soup.select_one('div[data-testid="User-Name"]')
        if author_elem:
            metadata["author"] = author_elem.get_text(strip=True)
        
        # 从 URL 提取 handle
        match = re.search(r'x\.com/([^/]+)/', url)
        if match:
            metadata["author_handle"] = f"@{match.group(1)}"
        
        # 提取时间
        time_elem = soup.select_one('time')
        if time_elem:
            metadata["created_at"] = time_elem.get('datetime', '')
        
        # 提取标题（使用第一条推文的前100字符）
        tweet_text = soup.select_one('div[data-testid="tweetText"]')
        if tweet_text:
            text = tweet_text.get_text(strip=True)
            metadata["title"] = text[:100] + "..." if len(text) > 100 else text
        
        return metadata
    
    def _extract_media(self, soup: BeautifulSoup) -> Dict:
        """提取所有媒体资源"""
        images = []
        videos = []
        
        # 提取图片
        for img in soup.select('img[src*="media"]'):
            src = img.get('src', '')
            if src and src not in images:
                # 获取原图链接（去除尺寸参数）
                src = re.sub(r'&name=\w+', '&name=large', src)
                images.append(src)
        
        # 提取视频
        for video in soup.select('video'):
            src = video.get('src', '') or video.get('poster', '')
            if src and src not in videos:
                videos.append(src)
        
        return {
            "images": images,
            "videos": videos
        }
