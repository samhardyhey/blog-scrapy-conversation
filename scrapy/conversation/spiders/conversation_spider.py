from bs4 import BeautifulSoup
from dateutil import parser

import scrapy

# todo
# paginated article listing - using /articles suffix
# expand syndicate
# conversation defined URI?


class ConversationSpider(scrapy.Spider):
    name = "conversation"
    start_urls = [
        # 'https://theconversation.com/au/arts',
        # 'https://theconversation.com/au/books',
        "https://theconversation.com/au/business",
        # 'https://theconversation.com/au/education',
        "https://theconversation.com/au/environment",
        # 'https://theconversation.com/au/health',
        "https://theconversation.com/au/politics",
        # 'https://theconversation.com/au/technology',
    ]

    def parse(self, response):
        # Debug: Print the response to see what we're working with
        self.logger.info(f"Parsing page: {response.url}")
        
        # Try multiple selectors to find article links
        article_links = []
        
        # Method 1: Look for links containing article IDs in the URL
        article_links.extend(response.xpath("//a[contains(@href, '/au/') and contains(@href, '-')]/@href").getall())
        
        # Method 2: Look for links in content summary blocks
        article_links.extend(response.xpath("//a[contains(@class, 'content-summary')]/@href").getall())
        
        # Method 3: Look for any links that might be articles
        article_links.extend(response.xpath("//a[contains(@href, 'theconversation.com') and not(contains(@href, 'cdn.')) and not(contains(@href, 'images.'))]/@href").getall())
        
        # Remove duplicates and filter
        article_links = list(set(article_links))
        article_links = [link for link in article_links if '/au/' in link and link.count('-') >= 2]
        
        self.logger.info(f"Found {len(article_links)} potential article links")
        
        if not article_links:
            self.logger.warning("No article links found. The website structure may have changed.")
            # Try to follow the articles page
            yield response.follow('/au/business/articles', self.parse_articles_page)
        else:
            yield from response.follow_all(article_links[:5], self.parse_article)  # Limit to first 5 for testing

    def parse_articles_page(self, response):
        """Parse the articles listing page."""
        self.logger.info(f"Parsing articles page: {response.url}")
        
        # Look for article links on the articles page
        article_links = response.xpath("//a[contains(@href, '/au/') and contains(@href, '-')]/@href").getall()
        article_links = list(set(article_links))
        article_links = [link for link in article_links if '/au/' in link and link.count('-') >= 2]
        
        self.logger.info(f"Found {len(article_links)} article links on articles page")
        
        if article_links:
            yield from response.follow_all(article_links[:5], self.parse_article)  # Limit to first 5 for testing
        else:
            self.logger.error("No article links found on articles page")

    def parse_article(self, response):
        """Parse individual article pages."""
        self.logger.info(f"Parsing article: {response.url}")
        
        # Try multiple selectors for each field
        author = (
            response.xpath('//*[contains(concat( " ", @class, " " ), concat( " ", "author-name", " " ))]/text()').get() or
            response.xpath('//*[contains(@class, "byline")]//text()').get() or
            response.xpath('//*[contains(@class, "author")]//text()').get() or
            "Unknown Author"
        )
        
        title = (
            response.xpath("//strong/text()").get() or
            response.xpath("//h1/text()").get() or
            response.xpath('//*[contains(@class, "title")]//text()').get() or
            "Unknown Title"
        )
        
        # Try to get published date
        published_text = response.xpath("//time/text()").get()
        published = None
        if published_text:
            try:
                published = parser.parse(" ".join(published_text.split(" ")[1:-1][::-1]))
            except:
                published = None
        
        # Try to get topics
        topics_elements = (
            response.xpath('//*[contains(concat( " ", @class, " " ), concat( " ", "topic-list-item", " " ))]').getall() or
            response.xpath('//*[contains(@class, "topic")]').getall() or
            []
        )
        topics = "|".join([BeautifulSoup(e, "lxml").text.strip() for e in topics_elements]) if topics_elements else ""
        
        # Try to get article content
        article_elements = (
            response.xpath('//*[contains(concat( " ", @class, " " ), concat( " ", "inline-promos", " " ))]//p | //h2').getall() or
            response.xpath('//article//p').getall() or
            response.xpath('//*[contains(@class, "content")]//p').getall() or
            []
        )
        
        article_text = []
        for element in article_elements:
            text = BeautifulSoup(element, "lxml").text.strip()
            if text and all(skip not in text for skip in ["Read more", "Review", "Subscribe", "Donate"]):
                article_text.append(text)
        
        article = "\n".join(article_text) if article_text else "No content found"
        
        # Clean up the data
        author = author.strip() if author else "Unknown Author"
        title = title.strip() if title else "Unknown Title"
        
        self.logger.info(f"Extracted article: {title[:50]}... by {author}")
        
        yield {
            "author": author,
            "article_title": title,
            "article": article,
            "published": published,
            "url": response.url,
            "topics": topics,
        }
