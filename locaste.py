# coding: utf-8
"""
@author: Uraiz ali
"""
import json
import re
from copy import deepcopy

from scrapy import Request

from scrapyproduct.items import ProductItem, SizeItem
from scrapyproduct.spiderlib import SSBaseSpider
from scrapyproduct.toolbox import (extract_text_nodes, category_mini_item,
                                   unescape_html, is_valid_gtin)


class JpLocasteSpider(SSBaseSpider):

    Jp_seen_base_sku = set()

    def start_requests(self):
        countries_info = [
            ('jp', 'JPY', 'ja', 'https://www.lacoste.jp'),
        ]

        for country_code, currency, language, url in countries_info:
            meta = {
                'country_code': country_code,
                'currency': currency,
                'language_code': language,
                'dont_merge_cookies': True
            }

            yield Request(url, self.parse_homepage_jp, meta=meta)

    def parse_homepage_jp(self, response):
        navigation = self.extract_page_json(response)[0]

        for category in navigation['navigationProps']['menuItems']:
            for level1 in category.get('items', []):
                yield self.make_categories_request_jp(response, [level1])

                for level2 in level1.get('items', []):
                    yield self.make_categories_request_jp(response, [level1, level2])

                    for level3 in level2.get('items', []):
                        yield self.make_categories_request_jp(response, [level1, level2, level3])

    def make_categories_request_jp(self, response, selectors):
        meta = deepcopy(response.meta)
        meta['categories'] = [sel['title'] for sel in selectors]
        meta['products_count'] = selectors[-1].get('productsCount', 0)
        url = selectors[-1].get('linkUrl', '')
        return Request(response.urljoin(url), self.parse_products_jp, meta=meta, dont_filter=True)

    def parse_products_jp(self, response):
        for product in response.css('.cWDwrI'):
            url = product.css('::attr(href)').extract_first()
            if not url:
                continue
            base_sku = url.split('/')[-2]
            item = ProductItem(
                url=response.urljoin(url),
                referer_url=response.url,
                base_sku=base_sku,
                category_names=response.meta['categories'],
                country_code=response.meta['country_code'],
                language_code=response.meta['language_code'],
                currency=response.meta['currency'],
                brand='Lacoste',
                color_code=url.split('/')[-1]
            )

            yield category_mini_item(item)

            country_base_sku = '{}_{}'.format(
                response.meta['country_code'], item['base_sku'])
            if country_base_sku in self.Jp_seen_base_sku:
                continue
            self.Jp_seen_base_sku.add(country_base_sku)
            meta = deepcopy(response.meta)
            meta['item'] = item
            yield Request(item['url'], meta=meta, callback=self.parse_detail_jp)

        yield self.pagination_request_jp(response)

    def pagination_request_jp(self, response):
        meta = deepcopy(response.meta)
        meta['pagination'] = True
        url = response.css('.ifZDtx::attr(href)').extract()
        return Request(response.urljoin(url[-1]), self.parse_products_jp, meta=meta) \
            if url else None

    def parse_detail_jp(self, response):
        item = response.meta['item']
        item['title'] = response.css(
            '.Title__PDPTitleH1-sc-1rq47k2-0::text').extract_first()
        self.set_description_jp(response, item)
        product_json = self.extract_page_json(response)[0]['mainProps']
        product_detail = product_json['containerProps'][0]['containerProps'][1]['productResponse']
        product = product_detail['product']

        color_mapping = {}
        color_groups = product_detail['rdGroups']

        for options in color_groups:
            for selected_col in options['items']:
                if selected_col['itemType'] != 'ZozoSpecificColor':
                    continue
                color_mapping[selected_col['code']] = selected_col['longName']

        colors = self.extract_color_items(product)
        for color_code, color in colors.iteritems():
            color_item = deepcopy(item)
            color_name = [color_mapping[value] for value in color['color_name']
                          if value in color_mapping]
            color_item['color_name'] = color_name[0] if color_name else color_code
            color_item['color_code'] = color_code
            color_item['size_infos'] = color['size_infos']
            color_item['image_urls'] = color.get('image_urls', [])
            color_item['identifier'] = '{}-{}'.format(
                color_item['base_sku'], color_code)
            color_item['image_urls'] = [
                response.urljoin(img['id']) for img in product['images']
                if img['imageCode'] == color_item['identifier']
            ]
            color_item['available'] = bool(color_item['size_infos'])
            color_item['url'] = color_item['url'].replace(
                item['color_code'], color_item['color_code']
            )
            yield color_item

    def set_description_jp(self, response, item):
        description = extract_text_nodes(response.css(
            '.Description__WP-sc-1gh8qm1-3')) or 'N/A'
        item['description_text'] = description

    def set_images_jp(self, response, item):
        image_urls = response.css(
            '.Desktop__Thumbnail-sc-64dv4-3 img::attr(src)').extract()
        item['image_urls'] = [response.urljoin(img.replace('.cs.jpg', '.zm.jpg'))
                              for img in image_urls]

    def extract_page_json(self, response):
        data = response.css('#__NEXT_DATA__::text').extract_first()
        try:
            return json.loads(data)['props']['initialProps']['pageProps']['containerProps']
        except ValueError:
            return {}

    def extract_color_items(self, product):
        colors = dict()
        for sku in product['variants']:
            if not sku.get('inInventory'):
                continue

            color_name = self.extract_filter(
                sku, 'zozospecificcolor', 'filterProperties')
            color_name = color_name or []
            color_code = self.extract_filter(
                sku, 'colorcode', 'filterProperties')[0]

            colors.setdefault(color_code, {})
            colors[color_code].setdefault('size_infos', [])
            colors[color_code].setdefault('color_name', color_name)

            size_name = self.extract_filter(
                sku, 'japansize', 'extraProperties')
            size_name_two = self.extract_filter(
                sku, 'sizecode', 'filterProperties')

            final_size_name = size_name[0] if size_name else size_name_two[0]
            size_item = SizeItem(
                stock=1,
                size_name=final_size_name,
                size_identifier=final_size_name,
                size_current_price_text=sku['sumUp']['discounted']['amountWithTax'],
                size_original_price_text=sku['sumUp']['prime']['amountWithTax']
            )
            gtin = sku.get('articleCode')
            if gtin:
                size_item['size_gtin'] = gtin

            colors[color_code]['size_infos'].append(size_item)
        return colors

    def extract_filter(self, sku, required_filter, filter_title):
        for attr in sku[filter_title]:
            if attr['field'].lower() != required_filter:
                continue
            return [attr['values'][0]] if required_filter != 'zozospecificcolor' else attr['values']


class TrLocasteSpider(SSBaseSpider):
    country = ''
    max_stock_level = 1
    seen_base_sku = set()
    color_url_t = '{}?integration_renk={}'
    nav_url = 'https://www.lacoste.com.tr/menus/generate/?format=json&depth_height=3&include_parent=true'

    def start_requests(self):
        countries_info = [
            ('tr', 'TRY', 'tr', 'https://www.lacoste.com.tr/'),
        ]

        for country_code, currency, language, url in countries_info:
            if self.country and country_code not in self.country:
                continue

            meta = {
                'country_code': country_code,
                'currency': currency,
                'language_code': language,
                'dont_merge_cookies': True
            }

            yield Request(self.nav_url, self.parse_homepage_tr, meta=meta)

    def parse_homepage_tr(self, response):
        raw_json = json.loads(response.text)

        for row in raw_json['menu']:
            if row['level'] == 0:
                categories = [row['label']]

            elif row['level'] == 1:
                categories = [row['parent']['label'], row['label']]

            else:
                categories = [row['parent']['parent']['label'],
                              row['parent']['label'], row['label']]

            url = response.urljoin(row['url'])
            meta = deepcopy(response.meta)
            meta['categories'] = categories
            yield Request(url, self.parse_products_tr, meta=meta)

    def parse_products_tr(self, response):
        for product in response.css('.product-item-box'):
            url = product.css(
                '.product-item-image-link::attr(href)').extract_first()
            if not url:
                continue
            base_sku = self.get_base_sku(url)

            item = ProductItem(
                url=response.urljoin(url),
                referer_url=response.url,
                base_sku=base_sku,
                category_names=response.meta['categories'],
                country_code=response.meta['country_code'],
                language_code=response.meta['language_code'],
                currency=response.meta['currency'],
                brand='Lacoste'
            )

            yield category_mini_item(item)

            meta = deepcopy(response.meta)
            meta['item'] = item
            yield Request(item['url'], meta=meta, callback=self.parse_siblings)

        if 'pagination' in response.meta:
            return

        for request in self.make_pagination_requests_tr(response):
            yield request

    def make_pagination_requests_tr(self, response):
        total_page = response.css('.pagination-item::text').extract()
        if total_page:
            total_page = int(total_page[-1].strip())
            for i in xrange(2, total_page + 1):
                url = u'{}?page={}'.format(response.url, i)
                meta = deepcopy(response.meta)
                meta['pagination'] = True
                yield Request(url, self.parse_products_tr, meta=meta, dont_filter=True)

    def parse_siblings(self, response):
        for color in response.css('.variant-colors a:not(.is-disable)'):
            product_code = self.get_product_code(color)
            color_item = deepcopy(response.meta['item'])
            color_item['url'] = self.color_url_t.format(
                response.url, product_code)
            color_item['color_code'] = product_code
            color_item['identifier'] = u'{}-{}'.format(
                color_item['base_sku'], color_item['color_code'])
            if color_item['identifier'] in self.seen_base_sku:
                continue

            self.seen_base_sku.add(color_item['identifier'])
            meta = {'item': color_item}
            yield Request(color_item['url'], self.parse_product_tr, meta=meta)

    def parse_product_tr(self, response):
        item = response.meta['item']
        item['title'] = extract_text_nodes(
            response.css('.m-detail-section .name'))[0]
        item['description_text'] = extract_text_nodes(
            response.css('.product-detail-wrapper .content'))
        item['color_name'] = response.css('.product-variant .selected-type strong::text').extract_first() \
            or item['color_code']
        item['image_urls'] = response.css(
            '.js-popup-image__toggle img::attr(src)').extract()
        self.set_price_tr(response, item)
        has_sizes = response.css('.variant-sizes.dropdown a')
        if has_sizes:
            self.set_size_tr(response, item)
            item['available'] = any(size['stock']
                                    for size in item['size_infos'])
            if item['available']:
                yield item
            return

        item['available'] = False if response.css(
            '.product-button--disabled') else True
        item['product_stock'] = int(item['available'])
        yield item

    def get_base_sku(self, url):
        for base_sku in url.split('-'):
            if re.search('\d\d\d', base_sku):
                return base_sku.strip('/')

    def get_product_code(self, color):
        product_code = color.css(
            '::attr(data-value)').extract_first('').strip('-')
        if not product_code:
            product_code = color.css(
                '::attr(data-pk)').extract_first('').strip()
        return product_code

    def set_price_tr(self, response, item):
        old_price = response.css(
            '.m-detail-section .old-price::text').extract_first()
        sale_price = response.css(
            '.m-detail-section .current-price::text').extract_first()
        if old_price:
            item['old_price_text'] = old_price
            item['new_price_text'] = sale_price
        else:
            item['full_price_text'] = sale_price

    def set_size_tr(self, response, item):
        sizes = extract_text_nodes(response.css('.variant-sizes.dropdown a'))
        for size in sizes:
            size_name = size.replace(' Stokta Yok', '').strip('-')
            size_info = SizeItem(
                size_name=size_name,
                size_identifier=size_name,
                stock=0 if 'Stokta Yok' in size else 1
            )
            item['size_infos'].append(size_info)


class LocasteSpider(JpLocasteSpider, TrLocasteSpider):
    name = 'locaste'
    long_name = 'lacoste.com'
    base_url = 'http://www.lacoste.com/'
    version = '1.1.0'
    country = ''

    def __init__(self, *args, **kwargs):
        super(LocasteSpider, self).__init__(*args, **kwargs)
        self.country = self.country.lower().split(',')
        self.country = {s.strip() for s in self.country if s.strip()}

    def start_requests(self):
        for base in self.__class__.__bases__:
            for req in base.start_requests(self):
                yield req
