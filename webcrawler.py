#!/usr/bin/env python

from urllib.parse import urlparse, urljoin
from gevent.queue import Queue
import gevent
import gevent.monkey
import lxml.html
import requests
import mimetypes
import pprint
import argparse
import sys

gevent.monkey.patch_socket()

TIMEOUT = 3
THREADS = 20
 
class Crawler():
    def __init__(self, rooturl):
        self.rooturl = rooturl
        self.netloc = urlparse(rooturl).netloc
        self.queue = Queue()
        self.sitemap = {}

    def fetch_data(self, url):
        """
        url: should be full URL
        Makes request to the given url.
        If status code not equal 200 delete link from sitemap.
        Stops execution in case of failed request.
        """
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.content
            else:
                del self.sitemap[url]
                return None
        except requests.exceptions.RequestException as e:
            print("%s: %s" % (url, e))
            sys.exit(1)

    def get_links(self, page):
        """
        Parser of valid links on the given page.
        page: should be HTML content.
        Returns set with links on current page.
        """
        tree = lxml.html.fromstring(page)
        valid_links = []
        links = tree.xpath('//a/@href')
        for link in links:
            #In real world nobody would hardcode link but who knows ;)
            fullurl = urljoin(self.rooturl, link)
            if urlparse(fullurl).netloc == self.netloc:
                # Try to guess mimetype based on URL and
                # add only HTML or unknown type to links list.
                mimetype = mimetypes.guess_type(fullurl)[0]
                if not mimetype or mimetype == 'text/html':
                    valid_links.append(fullurl.split("#")[0])
        return set(valid_links)

    def get_assets(self, page):
        """
        Parser of assets on the giving page.
        page: should be HTML content.
        Returns set with assets on current page.
        """
        tree = lxml.html.fromstring(page)
        img = [urljoin(self.rooturl, path) for path in tree.xpath('//img/@src')]
        css = [urljoin(self.rooturl, path) for path in tree.xpath('//link/@href')]
        js = [urljoin(self.rooturl, path) for path in tree.xpath('//script/@src')]
        return set(img + css + js)

    def worker(self):
        """
        Gevent worker for parallel execution.
        Fills sitemap with assets and child links and adds
        link absent in initial sitemap to execution queue.
        """
        while not self.queue.empty():
            url = self.queue.get()
            data = self.fetch_data(url)
            if data:
                links = self.get_links(data)
                assets = self.get_assets(data)
                self.sitemap[url]['links'] = links
                self.sitemap[url]['assets'] = assets
                for link in links:
                    if link not in self.sitemap:
                        self.sitemap[link] = {}
                        self.queue.put(link)

    def run(self):
        """
        Main method that's parse root or any other given URL and
        builds an initial sitemap, fills queue and spawn workers.
        """
        data = self.fetch_data(self.rooturl)
        if data:
            self.sitemap = {link:{} for link in self.get_links(data)}
            for link in self.sitemap.keys():
                self.queue.put(link)
            gevent.joinall([gevent.spawn(self.worker) for i in range(THREADS)])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', dest='url', help='root URL', required=True)
    args = parser.parse_args()
    crowler = Crawler(args.url)
    crowler.run()
    pprint.pprint(crowler.sitemap) # A little bit buggy library but ok to print dict to stdout
