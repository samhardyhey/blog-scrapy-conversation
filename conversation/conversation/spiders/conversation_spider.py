import scrapy
from bs4 import BeautifulSoup
from dateutil import parser

# todo
# paginated article listing - using /articles suffix
# expand syndicate
# conversation defined URI?


class ConversationSpider(scrapy.Spider):
    name = "conversation"
    start_urls = [
        # 'https://theconversation.com/au/arts',
        # 'https://theconversation.com/au/books',
        'https://theconversation.com/au/business',
        # 'https://theconversation.com/au/education',
        'https://theconversation.com/au/environment',
        # 'https://theconversation.com/au/health',
        'https://theconversation.com/au/politics',
        # 'https://theconversation.com/au/technology',
    ]

    def parse(self, response):
        article_links = response.xpath(
            "//a[@class='article-link']/@href")
        yield from response.follow_all(article_links, self.parse_article)

    def parse_article(self, response):
        # slightly more complex parses
        published = response.xpath('//time/text()').get()
        published = parser.parse(' '.join(published.split(' ')[1:-1][::-1]))

        topics = response.xpath(
            '//*[contains(concat( " ", @class, " " ), concat( " ", "topic-list-item", " " ))]').getall()
        topics = '|'.join([BeautifulSoup(e, 'lxml').text.strip()
                          for e in topics])

        article = response.xpath(
            '//*[contains(concat( " ", @class, " " ), concat( " ", "inline-promos", " " ))]//p | //h2').getall()
        article = [BeautifulSoup(e, 'lxml').text.strip() for e in article]
        article = [p for p in article if all(
            skip not in p for skip in ['Read more', 'Review'])]
        article = '\n'.join(article)

        yield {
            'author': response.xpath(
                '//*[contains(concat( " ", @class, " " ), concat( " ", "author-name", " " ))]/text()').get().strip(),
            'article_title': response.xpath('//strong/text()').get().strip(),
            'article': article,
            'published': published,
            'url': response.url,
            'topics': topics
        }
