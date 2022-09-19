import scrapy


class ConversationSpider(scrapy.Spider):
    name = "conversation"
    start_urls = [
        'https://theconversation.com/au',
    ]

    def parse(self, response):
        article_links = response.xpath("//a[@class='article-link']/@href")
        yield from response.follow_all(article_links, self.parse_article)

    def parse_article(self, response):
        yield {
            'author': response.xpath(
                '//*[contains(concat( " ", @class, " " ), concat( " ", "author-name", " " ))]/text()').get(),
            'article_title': response.xpath('//strong/text()').get(),
            'article': response.xpath('//*[contains(concat( " ", @class, " " ), concat( " ", "inline-promos", " " ))]/p/text()').getall(),
            'published': response.xpath('//time/text()').get(),
            'url': response.url,
            'topics': response.xpath('//*[contains(concat( " ", @class, " " ), concat( " ", "topic-list-item", " " ))]').getall(),
        }
