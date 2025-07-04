from bs4 import BeautifulSoup
from dateutil import parser
import re
from urllib.parse import urlparse

import scrapy

# todo
# paginated article listing - using /articles suffix
# expand syndicate

class ConversationSpider(scrapy.Spider):
    name = "conversation"
    start_urls = [
        'https://theconversation.com/au/arts',
        'https://theconversation.com/au/books',
        "https://theconversation.com/au/business",
        'https://theconversation.com/au/education',
        "https://theconversation.com/au/environment",
        'https://theconversation.com/au/health',
        "https://theconversation.com/au/politics",
        'https://theconversation.com/au/technology',
    ]

    def parse(self, response):
        self.logger.info(f"Parsing page: {response.url}")
        # Extract section from the URL (e.g., /au/arts -> arts)
        path = urlparse(response.url).path
        path_parts = path.split("/")
        if len(path_parts) >= 3 and path_parts[1] == 'au':
            section = path_parts[2]  # Get the section after /au/
        else:
            section = path_parts[-1] if path_parts[-1] else path_parts[-2]
        # Get all <a> tags with href containing 'theconversation.com' and '-'
        article_links = response.xpath("//a[contains(@href, 'theconversation.com') and contains(@href, '-')]/@href").getall()
        article_links = [link for link in article_links if re.search(r'-\d+$', link)
                        and not any(skip in link for skip in ['cdn.', 'images.', '/au/topics/', '/au/events/', '/au/terms', '/au/who-we-are', '/au/resources'])]
        article_links = list(set(article_links))
        self.logger.info(f"Found {len(article_links)} actual article links")
        if not article_links:
            self.logger.warning("No article links found. The website structure may have changed.")
            yield response.follow('/au/business/articles', self.parse_articles_page, meta={'source_section': section})
        else:
            for link in article_links[:10]:  # Limit to first 10 for testing
                yield response.follow(link, self.parse_article, meta={'source_section': section})

    def parse_articles_page(self, response):
        self.logger.info(f"Parsing articles page: {response.url}")
        path = urlparse(response.url).path
        path_parts = path.split("/")
        if len(path_parts) >= 3 and path_parts[1] == 'au':
            section = path_parts[2]  # Get the section after /au/
        else:
            section = path_parts[-1] if path_parts[-1] else path_parts[-2]
        article_links = response.xpath("//a[contains(@href, 'theconversation.com') and contains(@href, '-')]/@href").getall()
        article_links = [link for link in article_links if re.search(r'-\d+$', link)
                        and not any(skip in link for skip in ['cdn.', 'images.', '/au/topics/', '/au/events/', '/au/terms', '/au/who-we-are', '/au/resources'])]
        article_links = list(set(article_links))
        self.logger.info(f"Found {len(article_links)} article links on articles page")
        if article_links:
            for link in article_links[:10]:
                yield response.follow(link, self.parse_article, meta={'source_section': section})
        else:
            self.logger.error("No article links found on articles page")

    def parse_article(self, response):
        self.logger.info(f"Parsing article: {response.url}")
        section = response.meta.get('source_section', '')
        # Try multiple selectors for author
        author = (
            response.xpath('//*[contains(@class, "author-name")]/text()').get() or
            response.xpath('//*[contains(@class, "byline")]//text()').get() or
            response.xpath('//*[contains(@class, "author")]//text()').get() or
            response.xpath('//*[contains(@class, "contributor")]//text()').get() or
            "Unknown Author"
        )
        
        # Try multiple selectors for title
        title = (
            response.xpath('//h1[contains(@class, "entry-title")]//strong/text()').get() or
            response.xpath('//h1[contains(@class, "entry-title")]//text()').get() or
            response.xpath('//h1[contains(@class, "legacy")]//strong/text()').get() or
            response.xpath('//h1[contains(@class, "legacy")]//text()').get() or
            response.xpath('//meta[@property="og:title"]/@content').get() or
            response.xpath('//h1/text()').get() or
            response.xpath('//*[contains(@class, "headline")]//text()').get() or
            response.xpath('//*[contains(@class, "title")]//text()').get() or
            response.xpath('//*[contains(@class, "article-title")]//text()').get() or
            "Unknown Title"
        )
        
        # Try to get published date
        published_text = (
            response.xpath('//time/text()').get() or
            response.xpath('//*[contains(@class, "published")]//text()').get() or
            response.xpath('//*[contains(@class, "date")]//text()').get()
        )
        published = None
        if published_text:
            try:
                published = parser.parse(published_text.strip())
            except:
                try:
                    # Try the old format
                    published = parser.parse(" ".join(published_text.split(" ")[1:-1][::-1]))
                except:
                    published = None
        
        # Try to get topics
        topics_elements = (
            response.xpath('//*[contains(@class, "topic-list-item")]').getall() or
            response.xpath('//*[contains(@class, "topic")]').getall() or
            response.xpath('//*[contains(@class, "tag")]').getall() or
            []
        )
        topics = "|".join([BeautifulSoup(e, "lxml").text.strip() for e in topics_elements]) if topics_elements else ""
        
        # Try to get article content - multiple strategies
        article_text = []
        
        # Strategy 1: Look for article content in specific containers
        content_selectors = [
            '//article//p',
            '//*[contains(@class, "content")]//p',
            '//*[contains(@class, "article-content")]//p',
            '//*[contains(@class, "body")]//p',
            '//*[contains(@class, "text")]//p',
            '//div[contains(@class, "content")]//p',
            '//div[contains(@class, "article")]//p'
        ]
        
        for selector in content_selectors:
            elements = response.xpath(selector).getall()
            if elements:
                for element in elements:
                    text = BeautifulSoup(element, "lxml").text.strip()
                    if text and len(text) > 20:  # Only include substantial text
                        if all(skip not in text.lower() for skip in ["read more", "review", "subscribe", "donate", "sign up", "newsletter"]):
                            article_text.append(text)
                if article_text:  # If we found content, break
                    break
        
        # Strategy 2: If no content found, try broader selectors
        if not article_text:
            broad_selectors = [
                '//p[not(ancestor::header) and not(ancestor::footer) and not(ancestor::nav)]',
                '//div[contains(@class, "text")]//text()',
                '//div[contains(@class, "content")]//text()'
            ]
            
            for selector in broad_selectors:
                elements = response.xpath(selector).getall()
                if elements:
                    for element in elements:
                        text = BeautifulSoup(element, "lxml").text.strip()
                        if text and len(text) > 50:  # Longer text for broader selectors
                            if all(skip not in text.lower() for skip in ["read more", "review", "subscribe", "donate", "sign up", "newsletter", "cookie", "privacy"]):
                                article_text.append(text)
                    if article_text:
                        break
        
        article = "\n\n".join(article_text) if article_text else "No content found"
        
        # Clean up the data
        author = author.strip() if author else "Unknown Author"
        title = title.strip() if title else "Unknown Title"
        
        self.logger.info(f"Extracted article: {title[:50]}... by {author} (content length: {len(article)})")
        
        yield {
            "author": author,
            "article_title": title,
            "article": article,
            "published": published,
            "url": response.url,
            "topics": topics,
            "source_section": section,
        }
