# coding: utf-8

"""
Scrapy spider for MarkaVIP.
@author: uraiz ali
"""

import json
from copy import deepcopy

from scrapy import Request

from scrapyproduct.items import ProductItem, SizeItem
from scrapyproduct.spiderlib import SSBaseSpider
from scrapyproduct.toolbox import (
    register_deliveryregion,
    category_mini_item,
    extract_text_nodes,
)


class MarkaVIPSpider(SSBaseSpider):
    """Scrapy spider for MarkaVIP"""
    name = 'markavi'
    long_name = 'MarkaVIP'
    base_url = 'https://markavip.com/'

    single_item_test = False

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
        item = response.meta

        for level1 in response.css('.header-nav-wrap li'):
            titel1 = level1.css('.nav-item::text').extract_first()
            url1 = level1.css('.nav-item::attr(href)').extract_first()

            if self.is_valid_url(url1):
                item['categories'] = [titel1]
                yield Request(response.urljoin(url1), self.parse_products, meta=item)

            for level2 in level1.css('dl'):
                title2 = level2.css('.fn-bold a::text').extract_first()
                url2 = level2.css('.fn-bold a::attr(href)').extract_first()

                if self.is_valid_url(url2):
                    item['categories'] = [titel1, title2]
                    yield Request(response.urljoin(url2), self.parse_products, meta=item)

                for level3 in level2.css('dd:not(.fn-bold) a'):
                    title3 = level3.css('::text').extract_first()
                    url3 = level3.css('::attr(href)').extract_first()

                    if self.is_valid_url(url3):
                        item['categories'] = [titel1, title2, title3]
                        yield Request(response.urljoin(url3), self.parse_products, meta=item)

    def parse_products(self, response):
        for product in response.css('#J-pro-list > li'):
            item = ProductItem(
                url=response.urljoin(product.css('a::attr(href)').get()),
                base_sku=product.css('::attr(data-gid)').get(),
                referer_url=response.url,
                category_names=response.meta.get('categories', []),
                language_code='en',
                brand='markavip',
                country_code=response.meta.get('country_code'),
                currency=response.meta.get('currency')
            )
            mini_item = category_mini_item(item)
            yield mini_item

            yield Request(item['url'], self.parse_product_detail, meta={'item': item})

        self.parse_pagination(response)

    def parse_pagination(self, response):
        next_page = response.css('.ui-page-next::attr(href)').extract_first()
        if next_page:
            url = response.urljoin(next_page)
            return Request(url, self.parse_products, meta=response.meta)

    def parse_product_detail(self, response):
        item = response.meta['item']
        currency = response.css('.currency-site::text').get()
        if currency:
            item['currency'] = currency
        item['title'] = response.css('[itemprop="name"]::text').get()
        item['sku'] = response.css('[itemprop="identifier"]::text').get()
        item['use_size_level_prices'] = True
        colors = response.css('#J-sku a::text').getall()
        colors = colors or ['one_color']
        for color in colors:
            color_items = deepcopy(item)
            color_items['identifier'] = item['base_sku']+'_'+color
            color_items['color_name'] = color
            color_items['image_urls'] = response.css(
                '.goods-loading::attr(src)').getall()
            self.get_size_infos(response, color_items)

            yield color_items

    def is_valid_url(self, url):
        return url if 'javascript' not in url else None

    def get_size_infos(self, response, color_item):
        sizes = response.css('.J-size-list a::text').getall()
        sizes = sizes or ['one_size']
        for size in sizes:
            size_info = SizeItem(
                size_name=size,
                size_identifier=color_item['identifier']+'_'+size,
                stock=int(response.css('.stockNum::text').get(default=1)),
                size_original_price_text=str(
                    response.css('.J-sku-price span::text').get()),
                size_current_price_text=str(response.css(
                    '.org-price-box  del::text').get())
            )
            color_item['size_infos'].append(size_info)
