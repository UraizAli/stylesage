# coding: utf-8
"""
@author: Uraiz ali
"""
from copy import deepcopy

from scrapy import Request

from scrapyproduct.items import ProductItem, SizeItem
from scrapyproduct.spiderlib import SSBaseSpider
from scrapyproduct.toolbox import (category_mini_item)


class JpLocasteSpider(SSBaseSpider):
    country = ''
    seen_base_sku = set()
    countries = [
        ('jp', 'ja', 'JPY', 'https://www.lacoste.jp')
    ]

    def start_requests(self):
        for country_code, language_code, currency, url in self.countries:
            meta = {
                'country_code': country_code,
                'currency': currency,
                'language_code': language_code,
            }
            yield Request(url, callback=self.parse_homepage, meta=meta)

    def parse_homepage(self, response):
        for level1 in response.css('.htmlElements__Ul-sc-1e1gdav-4 li'):
            label1 = level1.css(
                '.text__TextBase-wvjikk-0::text').extract_first()

            for level2 in level1.css('.htmlElements__Ul-sc-1e1gdav-4 li'):
                label2 = level2.css(
                    '.MenuLinkList__H3-ki4j0-0.hoeBPK a::text').extract_first()
                url1 = level2.css(
                    '.MenuLinkList__H3-ki4j0-0.hoeBPK a::attr(href)').extract_first()
                if url1:
                    yield self.make_request(response, url1, [label1, label2])

                for level3 in level2.css('.htmlElements__Ul-sc-1e1gdav-4.fvRPJd li'):
                    label3 = level3.css('a::text').extract_first()
                    url2 = level3.css('a::attr(href)').extract_first()
                    if url2:
                        yield self.make_request(response, url2, [label1, label2, label3])

        categories_urls = response.css(
            '.text__MenuLinkCondensed-wvjikk-16.SidebarItem__MenuLink-dys11-6::attr(href)').extract()
        for url in categories_urls:
            catogaries = url.split('/')
            yield self.make_request(response, url, catogaries)

    def make_request(self, response, url, catogaries):
        if url:
            meta = deepcopy(response.meta)
            meta['categories'] = catogaries
            return Request(response.urljoin(url), callback=self.parse_product, meta=meta)
        return

    def parse_product(self, response):
        product_urls = response.css(
            '.htmlElements__ABlock-sc-1e1gdav-3::attr(href)').extract()

        for url in product_urls:
            base_sku = url.split('/')[2]
            item = ProductItem(
                url=response.urljoin(url),
                base_sku=base_sku,
                referer_url=response.url,
                category_names=response.meta.get('categories', []),
                language_code=response.meta.get('language_code'),
                brand='locaste',
                country_code=response.meta.get('country_code'),
                currency=response.meta.get('currency')
            )
            yield category_mini_item(item)

            if base_sku not in self.seen_base_sku:
                yield Request(item['url'], callback=self.parse_detail, meta={'item': item})
                self.seen_base_sku.add(base_sku)

        yield self.parse_pagination(response)

    def parse_pagination(self, response):
        next_page = response.css(
            '.htmlElements__ABlock-sc-1e1gdav-3.Pagination__Item-q8pzb8-2::attr(href)').extract_first()
        if next_page:
            return Request(response.urljoin(next_page), callback=self.parse_product, meta=response.meta)

    def parse_detail(self, response):
        item = response.meta['item']

        item['title'] = response.css(
            '.text__H1-wvjikk-2::text').extract_first()
        item['old_price_text'] = response.css(
            '.Price__PriceWrapper-sc-1tbjaoc-3.kmzMLF span:nth-child(1)::text').extract_first()
        item['new_price_text'] = response.css(
            '.Price__PriceWrapper-sc-1tbjaoc-3.kmzMLF span:nth-child(2)::text').extract_first()
        item['description_text'] = response.css(
            '.text__P-wvjikk-8.gwLbpb::text').extract()

        color_ids = response.css(
            '.ColorSwatch__List-sc-1k99ke9-0.hXiqCD span::text').extract()
        base_url = response.css(
            '[rel="canonical"]::attr(href)').extract_first()

        for color_id in color_ids:
            url = '{}/{}'.format(base_url, color_id.split('-')[1].strip())
            yield Request(url, callback=self.parse_color, meta={'item': item})

    def parse_color(self, response):
        color_item = response.meta['item']
        color_item['identifier'] = response.css(
            '.BuyingOptions__ProductIDContainer-t5r1de-0 p::text').extract_first()
        color_item['color_name'] = response.css(
            '.Content__ColorAndPrice-sc-1t9s0qv-1 p span::text').extract_first()
        color_item['image_urls'] = response.css(
            '.htmlElements__Ul-sc-1e1gdav-4 img::attr(src)').extract()
        color_item['size_infos'] = self.get_size_info(response, color_item)

        return color_item

    def get_size_info(self, response, color_item):
        size_info = []
        sizes = response.css('.Desktop__Item-sc-4ldu9m-4::text').extract()
        for size in sizes:
            size_item = {}
            size_item['name'] = size
            size_item['identifier'] = '{}_{}'.format(
                color_item['identifier'], size)
            size_info.append(size_item)
        return size_info


class TrLocasteSpider(SSBaseSpider):
    country = ''
    seen_base_sku = set()
    countries = [
        ('tr', 'TRY', 'tr', 'https://www.lacoste.com.tr/')
    ]

    def start_requests(self):
        for country_code, language_code, currency, url in self.countries:
            meta = {
                'country_code': country_code,
                'currency': currency,
                'language_code': language_code,
            }
            yield Request(url, callback=self.parse_homepage, meta=meta)

    def parse_homepage(self, response):
        for level1 in response.css('.js-navigation.navigation-list li'):
            label1 = level1.css('a span::text').extract_first()
            url1 = level1.css('a::attr(href)').extract_first()
            yield self.make_request(response, url1, [label1])

            for level2 in level1.css('.page-sidebar__lists div div ul'):
                label2 = level2.css('.hero a::text').extract_first()
                url2 = level2.css('.hero a::attr(href)').extract_first()
                yield self.make_request(response, url2, [label1, label2])

                for level3 in level1.css('.page-sidebar__lists div div ul'):
                    label3 = level3.css('li a::text').extract_first()
                    url3 = level3.css('li a::attr(href)').extract_first()
                    yield self.make_request(response, url3, [label1, label2, label3])

    def make_request(self, response, url, catogaries):
        if url:
            meta = deepcopy(response.meta)
            meta['categories'] = catogaries
            return Request(response.urljoin(url), callback=self.parse_product, meta=meta)
        return

    def parse_product(self, response):
        for product in response.css('.product-item-box'):
            url = product.css(
                '.product-item-image-link::attr(href)').extract_first()
            base_sku = product.css(
                '.product-item-wrapper::attr(data-sku)').extract_first()
            item = ProductItem(
                url=response.urljoin(url),
                base_sku=base_sku,
                referer_url=response.url,
                category_names=response.meta.get('categories', []),
                language_code=response.meta.get('language_code'),
                brand='locaste',
                country_code=response.meta.get('country_code'),
                currency=response.meta.get('currency')
            )
            yield category_mini_item(item)

            if base_sku not in self.seen_base_sku:
                yield Request(item['url'], callback=self.parse_detail, meta={'item': item})
                self.seen_base_sku.add(base_sku)

        yield self.parse_pagination(response)

    def parse_pagination(self, response):
        pages = response.css('.pagination a::text').extract()
        for page in pages:
            url = '?page={}'.format(page)
            return Request(response.urljoin(url), callback=self.parse_product, meta=response.meta)

    def parse_detail(self, response):
        item = response.meta['item']
        item['title'] = response.css(
            '.name.hidden-xs h1::text').extract_first()
        item['full_price_text'] = response.css(
            '.current-price::text').extract_first()
        item['description_text'] = response.css(
            '.content ul li::text').extract()

        color_ids = response.css(
            '.variant-colors__item::attr(data-value)').extract()
        base_url = response.css(
            '[rel="canonical"]::attr(href)').extract_first()
        for color_id in color_ids:
            url = '{}?integration_renk={}'.format(base_url, color_id)
            yield Request(url, callback=self.parse_color, meta={'item': item})

    def parse_color(self, response):
        color_item = response.meta['item']
        color_item['identifier'] = response.css(
            '.js-variant-color-type::attr(data-color)').extract_first()
        color_item['color_name'] = response.css(
            '.js-variant-color-type::text').extract_first()
        color_item['image_urls'] = response.css(
            '.product-detail__thumbnails img::attr(src)').extract()
        color_item['size_infos'] = self.get_size_info(response, color_item)

        return color_item

    def get_size_info(self, response, color_item):
        size_info = []
        sizes = response.css('.variant-sizes__item::text').extract()
        for size in sizes:
            size_item = {}
            size_item['name'] = size
            size_item['identifier'] = '{}_{}'.format(
                color_item['identifier'], size)
            size_info.append(size_item)
        return size_info


class LocasteSpider(JpLocasteSpider, TrLocasteSpider):
    name = 'laoste'
    long_name = 'lacoste.com'
    base_url = 'http://www.lacoste.com/'
    version = '1.0.0'
    country = ''

    def start_requests(self):
        for base in self.__class__.__bases__:
            for req in base.start_requests(self):
                yield req
