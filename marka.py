# coding: utf-8

"""
Scrapy spider for MarkaVIP.
@author: uraiz ali
"""

from copy import deepcopy

from scrapy import Request

from scrapyproduct.items import ProductItem, SizeItem
from scrapyproduct.spiderlib import SSBaseSpider
from scrapyproduct.toolbox import (category_mini_item, extract_links)


class MarkaVIPSpider(SSBaseSpider):
    """Scrapy spider for MarkaVIP"""
    name = 'markavi'
    long_name = 'MarkaVIP'
    base_url = 'https://markavip.com/'

    single_item_test = False
    seen_base_sku = set()

    country = ''
    version = '1.0.0'
    enabled_countries = ['sar']

    def test_single_item(self):
        item = ProductItem(
            base_sku='56158575',
            country_code='sa',
            language_code='en',
            currency='SAR',
            category_names=['Test cat'],
            url='https://markavip.com/p/versace-collection-mens-t-shirt-o-neck-short-sleeve-logo-pattern-casual-top-g0xdx0x4-rnc9gqc-xn-eoo-73.html?SPM=CAT.NEWIN.MEN.C3456',
            referer_url=None)
        return Request(item['url'], meta={'item': item}, callback=self.parse_product_detail)

    def start_requests(self):
        if self.single_item_test:
            yield self.test_single_item()
            return
        meta = {
            'country_code': 'sa',
            'language_code': 'en',
            'currency': 'SAR',
        }
        yield Request('http://www.markavip.com/?regioncode=sa', self.parse_homepage, meta=meta)

    def parse_homepage(self, response):
        for level1 in response.css('.header-nav-wrap li'):
            title1, url1 = extract_links(level1.css('.nav-item'))[0]
            yield self.make_requests(response, url1, [title1])

            for level2 in level1.css('dl'):
                title2, url2 = extract_links(level1.css('.fn-bold a'))[0]
                yield self.make_requests(response, url2, [title1, title2])

                for level3 in level2.css('dd:not(.fn-bold) a'):
                    title3, url3 = extract_links(level1.css(level3))[0]
                    yield self.make_requests(response, url3, [title1, title2, title3])

    def make_requests(self, response, url, categories):
        meta = deepcopy(response.meta)
        if self.is_valid_url(url):
            meta['categories'] = categories
            return Request(response.urljoin(url), self.parse_products, meta=meta)

    def parse_products(self, response):
        for product in response.css('#J-pro-list > li'):
            item = ProductItem(
                url=response.urljoin(product.css(
                    'a::attr(href)').extract_first()),
                base_sku=product.css('::attr(data-gid)').extract_first(),
                referer_url=response.url,
                category_names=response.meta.get('categories', []),
                language_code='en',
                brand='markavip',
                country_code=response.meta.get('country_code'),
                currency=response.meta.get('currency')
            )
            yield category_mini_item(item)
            if item['base_sku'] in self.seen_base_sku:
                continue
            self.seen_base_sku.add(item['base_sku'])
            yield Request(item['url'], self.parse_product_detail, meta={'item': item})

        yield self.parse_pagination(response)

    def parse_pagination(self, response):
        next_page = response.css('.ui-page-next::attr(href)').extract_first()
        if next_page:
            url = response.urljoin(next_page)
            return Request(url, self.parse_products, meta=response.meta)

    def parse_product_detail(self, response):
        item = response.meta['item']
        item['title'] = response.css('[itemprop="name"]::text').extract_first()
        item['identifier'] = response.css(
            '[itemprop="identifier"]::text').extract_first()
        item['description_text'] = response.css(
            '#detailHtml span::text').extract()

        item['full_price_text'] = response.css(
            '.J-sku-price span::text').extract_first()
        item['old_price_text'] = response.css(
            '.org-price-box  del::text').extract_first()
        color_ids = response.xpath(
            "//span[@data-key='Color']/@data-attrid").extract()
        item['use_size_level_prices'] = False

        self.get_currency(response)

        for color_id in color_ids:
            color_item = deepcopy(item)
            color_item['identifier'] = "{}_{}".format(
                item['identifier'], color_id)
            color_name_path = "//span[@data-key='Color' and @data-attrid='{}']/a/text()".format(
                color_id)
            color_item['color_name'] = response.xpath(
                color_name_path).extract_first('').strip()

            self.get_image_urls(response, color_id, color_item, color_ids)
            self.get_size_infos(response, color_item)

            yield color_item

    def is_valid_url(self, url):
        return url if 'javascript' not in url else None

    def get_size_infos(self, response, color_item):
        sizes = response.css('.J-size-list a::text').extract() or ['one_size']
        for size in sizes:
            size_info = SizeItem(
                size_name=size,
                size_identifier="{}_{}".format(color_item['identifier'], size),
                stock=int(response.css('.stockNum::text').get(default=1))
            )
            color_item['size_infos'].append(size_info)

    def get_image_urls(self, response, color_id, color_item, color_ids):
        img_path = "//span[@data-key='Color' and @data-attrid='{}']/img/@src".format(
            color_id)
        images = response.xpath(img_path).extract()
        color_item['image_urls'] = [
            img.replace('t.jpg', '.jpg').split('_')[0] for img in images
        ]
        if not color_item['image_urls'] or len(color_ids) == 1:
            color_item['image_urls'] = [img.replace('t.jpg', '.jpg').split('_')[0]
                                        for img in response.css('.goods-loading::attr(src)').extract()]

    def get_currency(self, response):
        item = response.meta['item']
        currency = response.css('.currency-site::text').extract_first()
        if currency:
            item['currency'] = currency
