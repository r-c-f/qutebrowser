#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Claude (longneck) <longneck@scratchbook.ch>
# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.


"""Tool to import data from other browsers.

Currently only importing bookmarks from Netscape Bookmark files is supported.
"""


import argparse
import inspect
import sys

_browser_default_input_format = {}


def main():
    #discover importer subclasses
    import_type = {}
    for name, obj in inspect.getmembers(
            sys.modules[__name__],
            lambda x: inspect.isclass(x) and
            issubclass(x, Importer) and
            x.format_
    ):
        import_type[obj.format_] = obj
        for browser in obj.browsers:
            _browser_default_input_format[browser] = obj.format_

    args = get_args()
    importer = import_type[args.input_format](
        path=args.bookmarks, browser=args.browser)
    importer.read()

    if args.bookmark_output:
        importer.print_bookmarks(args.import_bookmarks, args.import_keywords)
    elif args.quickmark_output:
        importer.print_quickmarks(args.import_bookmarks, args.import_keywords)
    elif args.search_output:
        if args.oldconfig:
            importer.print_qutebrowser_conf()
        else:
            importer.print_config_py()


def get_args():
    """Get the argparse parser."""
    parser = argparse.ArgumentParser(
        epilog="To import bookmarks from Chromium, Firefox or IE, "
        "export them to HTML in your browsers bookmark manager. ")
    parser.add_argument(
        'browser',
        help="Which browser? {%(choices)s}",
        choices=_browser_default_input_format.keys(),
        nargs='?',
        metavar='browser')
    parser.add_argument(
        '-i',
        '--input-format',
        help='Which input format? (overrides browser default)',
        choices=set(_browser_default_input_format.values()),
        required=False)
    parser.add_argument(
        '-b',
        '--bookmark-output',
        help="Output in bookmark format.",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '-q',
        '--quickmark-output',
        help="Output in quickmark format (default).",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '-s',
        '--search-output',
        help="Output config.py search engine format (negates -B and -K)",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '--oldconfig',
        help="Output search engine format for old qutebrowser.conf format",
        default=False,
        action='store_true',
        required=False)
    parser.add_argument(
        '-B',
        '--import-bookmarks',
        help="Import plain bookmarks (can be combiend with -K)",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '-K',
        '--import-keywords',
        help="Import keywords (can be combined with -B)",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument('bookmarks', help="Bookmarks file (html format)")
    args = parser.parse_args()
    #make sure we can assume proper input format
    if not args.input_format:
        if not args.browser:
            sys.exit("Must specify either browser or input format")
        args.input_format = _browser_default_input_format[args.browser]
    #create more intelligent default behavior
    if not args.search_output:
        if not (args.bookmark_output or
                args.quickmark_output):
            args.quickmark_output = True
        if not (args.import_bookmarks or
                args.import_keywords):
            args.import_bookmarks = True
            args.import_keywords = True
    return args


def dumb_search_escape(url):
    """Escape { and } in url. Dumb in that it ruins proper Qutebrowser URLs."""
    return url.replace('{', '{{').replace('}', '}}')


class Importer:
    """Base class for importers.

    Attributes:
        format_: Format name (used in arguments)
        browsers: Browsers supported
        _path: Path to bookmarks file or profile
        bookmarks: Dictionary mapping URLs to titles
        keywords: Dictionary mapping keywords to URL
        searchengines: Dictionary mapping keywords to URL in search format

    """

    format_ = None
    browsers = None

    def __init__(self, path=None, browser=None):
        """Initialize things.

        Args:
            path: Either a filesystem path or profile name
            browser:
                None: if path is a filesystem path
                {name} in self.browsers: if path is profile name to be guessed
        """
        self.bookmarks = {}
        self.keywords = {}
        self.searchengines = {}
        self._path = path
        if browser:
            self._guess_profile_path(browser)

    def _guess_profile_path(self, browser):
        """Guess profile path given browser name.

        Args:
            browser: name in self.browsers
        """
        raise NotImplementedError

    def read(self):
        """Read entries from filesystem."""
        raise NotImplementedError

    def print_config_py(self):
        """Print search engines in config.py format."""
        for search in self.searchengines.items():
            print('c.url.searchengines["{}"] = "{}"'.format(*search))

    def print_qutebrowser_conf(self):
        """Print search engines in qutebrowser.conf format."""
        for search in self.searchengines.items():
            print('{} = {}'.format(*search))

    def print_bookmarks(self, include_bookmarks, include_keywords):
        """Print boookmarks file.

        Args:
            include_bookmarks: Include self.bookmarks
            include_keywords: Include self.keywords
        """
        if include_bookmarks:
            for url, title in self.bookmarks.items():
                print(url, title)
        if include_keywords:
            for keyword, url in self.keywords.items():
                print(url, keyword)

    def print_quickmarks(self, include_bookmarks, include_keywords):
        """Print quickmarks file.

        Args:
            include_bookmarks: Include self.bookmarks
            include_keywords: Include self.keywords
        """
        if include_bookmarks:
            for url, title in self.bookmarks.items():
                print(title, url)
        if include_keywords:
            for keyword, url in self.keywords.items():
                print(keyword, url)


class NetscapeImporter(Importer):
    """Importer for Netscape HTML bookmarks files."""

    format_ = 'netscape'
    browsers = ['firefox', 'ie', 'chromium', 'seamonkey']

    def read(self):
        import bs4
        with open(self._path, encoding='utf-8') as f:
            soup = bs4.BeautifulSoup(f, 'html.parser')

        tags = soup.findAll(lambda tag: (
            (tag.name == 'a') and
            ('shortcuturl' in tag.attrs) and
            ('%s' in tag['href'])))
        for tag in tags:
            qburl = dumb_search_escape(tag['href']).replace('%s', '{}')
            self.searchengines[tag['shortcuturl']] = qburl
        tags = soup.findAll(lambda tag: (
            (tag.name == 'a') and
            ('shortcuturl' in tag.attrs) and
            ('%s' not in tag['href'])))
        for tag in tags:
            self.keywords[tag['shortcuturl']] = tag['href']
        tags = soup.findAll(lambda tag: (
            (tag.name == 'a') and
            ('shortcuturl' not in tag.attrs) and
            (tag.string)))
        for tag in tags:
            self.bookmarks[tag['href']] = tag.string


if __name__ == '__main__':
    main()
