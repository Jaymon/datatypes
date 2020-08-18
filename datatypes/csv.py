# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os
import codecs
import csv
import logging

from .compat import *
from . import environ
from .string import String, ByteString


logger = logging.getLogger(__name__)


class CSV(object):
    """Easily read/write the rows of a csv file
    :Example:
        # read a csv file
        c = CSV("/path/to/read/file.csv")
        for row in c:
            print(row)
        # write a csv file
        c = CSV("/path/to/write/file.csv")
        with c:
            for row in rows:
                c.add(row)
    """
    reader_class = csv.DictReader
    """the class that will be used by .create_reader()"""

    writer_class = csv.DictWriter
    """the class that will be used by .create_writer()"""

    rows_class = list
    """the class used in .rows()"""

    reader_row_class = None
    """You can set this to a class and rows returned from the default .normalize_reader_row()
    will be this type"""

    writer_row_class = None
    """You can set this to a class and rows returned from the default .normalize_writer_row()
    will be this type, this class should act like a dict unless you also change .writer_class"""

    class ContinueError(Exception):
        """Can be thrown to have CSV skip the current row"""
        pass

    def __init__(self, path, fieldnames=None, encoding="", **kwargs):
        """Create the csv instance
        :param path: string, the path to the csv file that will be read/written
        :param fieldnames: list, the fieldnames, when writing, if this is omitted
            then the keys of the first row dictionary passed to .add() will be used
            for the fieldnames. If omitted when reading then the first line of the
            csv file will be used for the fieldnames
        :param encoding: string, what character encoing to use
        """
        self.path = path
        self.fieldnames = fieldnames or []

        if not encoding:
            encoding = environ.ENCODING
        self.encoding = encoding

        cls = type(self)
        for k, v in kwargs.items():
            if hasattr(cls, k):
                setattr(self, k, v)

    def __iter__(self):
        logger.debug("Reading csv file: {}".format(self.path))

        with self.open() as f:
            self.reader = self.create_reader(f)
            for row in self.reader:
                try:
                    row = self.normalize_reader_row(row)
                    if row:
                        yield row

                except self.ContinueError:
                    pass

    def open(self, mode=""):
        """Mainly an internal method used for opening the file pointers needed for
        reading and writing
        :param mode: string, the open mode
        :returns: file pointer
        """
        if is_py2:
            if not mode:
                mode = "rb"
            return open(self.path, mode=mode)

        else:
            if not mode:
                mode = "r"
            return codecs.open(self.path, encoding=self.encoding, mode=mode)

    def __enter__(self):
        """Enables with context manager for writing"""
        logger.debug("Writing csv file: {}".format(self.path))
        f = self.open("ab+")
        self.writer = self.create_writer(f)
        return self

    def __exit__(self, exception_type, exception_val, trace):
        self.writer.f.close()

    def create_writer(self, f, **kwargs):
        kwargs.setdefault("dialect", csv.excel)
        kwargs.setdefault("restval", "")
        kwargs.setdefault("extrasaction", "ignore")
        kwargs.setdefault("quoting", csv.QUOTE_MINIMAL)
        kwargs.setdefault("fieldnames", self.fieldnames)
        #kwargs.setdefault("fieldnames", ["foo", "bar"])

        # from testdata CSVpath code:
        # in order to make unicode csvs work we are going to do a round about
        # thing where we write to a string buffer and then pull that out and write
        # it to the file, this is the only way I can make utf-8 work
        queue = self.normalize_writer_file(f)
        writer = self.writer_class(queue, **kwargs)
        writer.f = f
        writer.queue = queue
        writer.has_header = True if os.path.getsize(self.path) > 0 else False
        return writer

    def create_reader(self, f, **kwargs):
        """create a csv reader, this exists to make it easy to customize functionality,
        for example, you might have a csv file that doesn't have column headers, so you
        can override this method to pass in the column names, etc.
        :param f: io object, usually a file path opened with open()
        :returns: csv.Reader instance or something that acts like a built-in csv.Reader
            instance
        """
        kwargs.setdefault("fieldnames", self.fieldnames or None)
        kwargs.setdefault("dialect", csv.excel)

        f = self.normalize_reader_file(f)
        reader = self.reader_class(f, **kwargs)
        reader.f = f
        return reader

    def normalize_writer_file(self, f):
        queue = StringIO()
        return queue

    def normalize_reader_file(self, f):
        # https://stackoverflow.com/a/30031962/5006
        class FileWrapper(object):
            def __init__(self, f):
                self.f = f
                self.last_line = "" # will contain raw CSV row

            def __iter__(self):
                return self

            def __next__(self):
                self.last_line = next(self.f)
                return self.last_line
            next = __next__ # needed for py2? Python didn't consider it an iterator without next()

        return FileWrapper(f)

    def normalize_reader_row(self, row):
        """prepare row for reading, meant to be overridden in child classes if needed"""
        if is_py2:
            row = {String(k): String(v) for k, v in row.items()}

        if self.reader_row_class:
            row = self.reader_row_class(row)

        return row

    def normalize_writer_row(self, row):
        """prepare row for writing, meant to be overridden in child classes if needed"""

        row = {String(k): ByteString(v) for k, v in row.items()}

        if self.writer_row_class:
            row = self.writer_row_class(row)

        return row

    def add(self, row):
        writer = self.writer

        if not writer.has_header:
            if not self.fieldnames:
                self.fieldnames = list(row.keys())
            self.fieldnames = self.normalize_fieldnames(self.fieldnames)
            writer.fieldnames = self.fieldnames
            logger.debug("Writing fieldnames: {}".format(", ".join(self.fieldnames)))
            writer.writeheader()
            writer.has_header = True

        try:
            row = self.normalize_writer_row(row)
            if row:
                writer.writerow(row)
                data = writer.queue.getvalue()
                writer.f.write(data)
                writer.queue.truncate(0)
                writer.queue.seek(0)

        except self.ContinueError:
            pass

    def normalize_fieldnames(self, fieldnames):
        return fieldnames

    def find_fieldnames(self):
        """attempt to get the field names from the first line in the csv file"""
        with self.open() as f:
            reader = self.create_reader(f)
            return list(map(String, reader.fieldnames))

    def rows(self):
        """Return all the rows as a list"""
        return self.rows_class(self)

    def clear(self):
        """clear the csv file"""
        with self.open("wb") as f:
            f.truncate(0)

