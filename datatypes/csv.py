# -*- coding: utf-8 -*-
import os
import codecs
import csv
from contextlib import contextmanager
import io

from .compat import *
from .config.environ import environ
from .string import String, ByteString
from .utils import cbany
from .path import TempFilepath, Filepath
from . import logging


logger = logging.getLogger(__name__)


class CSVRow(Mapping):
    def __init__(self, columns, lookup):
        self.columns = columns
        self.lookup = lookup

    def __getitem__(self, k):
        return self.columns[self.lookup[k]]

    def __iter__(self):
        yield from self.lookup

    def __len__(self):
        return len(self.lookup)


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

    https://docs.python.org/3/library/csv.html
    """
#     reader_class = csv.DictReader
    """the class that will be used by .create_reader()"""

#     writer_class = csv.DictWriter
    """the class that will be used by .create_writer()"""

#     rows_class = list
    """the class used in .rows()"""

#     reader_row_class = None
    """You can set this to a class and rows returned from the default
    .normalize_reader_row() will be this type"""

#     writer_row_class = None
    """You can set this to a class and rows returned from the default
    .normalize_writer_row() will be this type, this class should act like a
    dict unless you also change .writer_class"""

#     class ContinueError(Exception):
#         """Can be thrown to have CSV skip the current row"""
#         pass

    def __init__(self, path, fieldnames=None, encoding="", **kwargs):
        """Create the csv instance
        :param path: str|IOBase, the path to the csv file that will be
            read/written :param fieldnames: list, the fieldnames, when writing,
            if this is. This can also already be a file pointer like object
            omitted then the keys of the first row dictionary passed to .add()
            will be used for the fieldnames. If omitted when reading then the
            first line of the csv file will be used for the fieldnames
        :param encoding: string, what character encoing to use
        :param **kwargs:
            strict: bool, pass in True (default False) to have the class check
                fieldnames when writing.
                https://docs.python.org/3/library/csv.html#csv.Dialect.strict
            extrasaction: str, "ignore" (default when strict is False) to
                ignore extra fields, "raise" (default when strict is True) to
                raise an error
            writer_mode: str, the default mode that will be passed to open a
                stream for writing
            readonly: bool, True if writing operations should fail
        """
        self.path = path
        self.set_fieldnames(fieldnames)
        #self.fieldnames = self.normalize_fieldnames(fieldnames)
        self.writer = None
        self.reader = None
        self.context_depth = 0 # protection against multiple context managers
        self.strict = kwargs.pop("strict", False)

        self.readonly = kwargs.pop("readonly", False)
        if self.readonly:
            self.writer_mode = kwargs.pop("writer_mode", "")

        else:
            self.writer_mode = kwargs.pop("writer_mode", "w+")
            #self.writer_mode = kwargs.pop("writer_mode", "wb+")

        if not encoding:
            encoding = environ.ENCODING
        self.encoding = encoding

#         cls = type(self)
#         for k, v in kwargs.items():
#             if hasattr(cls, k):
#                 setattr(self, k, v)

    def open(self, mode=""):
        """Mainly an internal method used for opening the file pointers needed
        for reading and writing

        :param mode: string, the open mode
        :returns: file pointer
        """
        if not mode or self.readonly:
            mode = "r"

        path = Filepath(self.path)

        logger.debug("Opening csv file: {} using mode: {}".format(
            path,
            mode,
        ))

        return path.open(mode=mode, encoding=self.encoding)

    @contextmanager
    def reading(self):
        """Internal method to manage reading operations

        :returns: IOBase, the file pointer ready to be fully read
        """
        if isinstance(self.path, io.IOBase):
            #logger.debug("Reading io: {}".format(self.path))
            tell = self.path.tell()
            self.path.seek(0)
            try:
                yield self.path

            finally:
                self.path.seek(tell)

        else:
            with self.open() as stream:
                yield stream

    @contextmanager
    def writing(self):
        """Internal method to manage writing operations

        :returns: IOBase, the file pointer ready to be written to
        """
        if self.readonly:
            raise IOError("CSV is in readonly mode")

        if isinstance(self.path, io.IOBase):
            #logger.debug("Writing io: {}".format(self.path.name))
            yield self.path

        else:
            with self.open(self.writer_mode) as stream:
                yield stream

    @contextmanager
    def appending(self, mode="a+"):
        """The default context manager truncates and write a new file, but that
        doesn't work for .add(), .append(), or .extend() so this provides an
        alternative context manager for appending to the file

        :param mode: str, the append mode that will be used to create the
            writer
        """
        prev_mode = self.writer_mode
        self.writer_mode = mode
        try:
            with self:
                yield self

        finally:
            self.writer_mode = prev_mode

    def __enter__(self):
        """Enables with context manager for writing"""
        self.context_depth += 1
        if not self.writer:
            #f = self.open(self.writer_mode)
            cm = self.writing()
            self.writer = self.create_writer(cm.__enter__())
            self.writer.cm = cm
        return self

    def __exit__(self, exception_type, exception_val, trace):
        self.context_depth -= 1
        if self.context_depth <= 0:
            self.writer.cm.__exit__(exception_type, exception_val, trace)
            self.writer = None
            self.context_depth = 0

    def create_writer(self, stream, **kwargs):
        kwargs.setdefault("dialect", csv.excel)
        kwargs.setdefault("restval", "")
        if self.strict:
            kwargs.setdefault("strict", True)
            kwargs.setdefault("extrasaction", "raise")
        else:
            kwargs.setdefault("strict", False)
            kwargs.setdefault("extrasaction", "ignore")
        kwargs.setdefault("quoting", csv.QUOTE_MINIMAL)
        kwargs.setdefault("fieldnames", self.fieldnames)

        stream = self.normalize_writer_stream(stream)
        writer = kwargs.pop("writer_class", csv.DictWriter)(stream, **kwargs)
        writer.has_header = True if stream.tell() > 0 else False
        return writer

    def create_reader(self, stream, **kwargs):
        """create a csv reader, this exists to make it easy to customize
        functionality, for example, you might have a csv file that doesn't have
        column headers, so you can override this method to pass in the column
        names, etc.

        :param stream: IOBase, usually a file path opened with open()
        :returns: csv.Reader instance or something that acts like a built-in
            csv.Reader instance
        """
        kwargs.setdefault("dialect", csv.excel)

        stream = self.normalize_reader_stream(stream)
        #reader = self.reader_class(stream, **kwargs)
        reader = kwargs.pop("reader_class", csv.reader)(stream, **kwargs)
        #reader.f = f
        return reader

    def add(self, row):
        """Add one row to the end of the CSV file

        This is the set interface

        :param row: dict, the row to be written
        """
        with self.appending():
            writer = self.writer
            if row := self.create_writer_row(row):
                if not writer.has_header:
                    if not self.fieldnames:
                        self.set_fieldnames(row.keys())
#                             self.fieldnames = self.normalize_fieldnames(
#                                 row.keys()
#                             )

                    writer.fieldnames = self.fieldnames
#                     writer.fieldnames = self.normalize_writer_fieldnames(
#                         self.fieldnames
#                     )
                    logger.debug("Writing fieldnames: {}".format(
                        ", ".join(self.fieldnames)
                    ))
                    writer.writeheader()
                    writer.has_header = True

                writer.writerow(row)

    def append(self, row):
        """Add one row to the end of the CSV file

        This is the list interface

        :param row: dict, the row to be written
        """
        return self.add(row)

    def extend(self, rows):
        """Add all the rows to the end of the csv file

        This is the list interface

        :param rows: list, all the rows
        """
        with self.appending():
            for row in rows:
                self.add(row)

    def update(self, rows):
        """Add all the rows to the end of the csv file

        This is the set and dict interface

        :param rows: list, all the rows
        """
        return self.extend(rows)

    def normalize_writer_stream(self, stream):
        return stream

    def normalize_reader_stream(self, stream):
        # https://stackoverflow.com/a/30031962
        return stream
#         class IOWrapper(io.IOBase):
#             def __init__(self, f):
#                 self.f = f
#                 self.last_line = "" # will contain raw CSV row
# 
#             def __next__(self):
#                 self.last_line = next(self.f)
#                 return self.last_line
# 
#             def __getattr__(self, k):
#                 return getattr(self.f, k)
# 
#         return IOWrapper(f)

    def create_reader_row(self, columns, **kwargs):
        """prepare row for reading, meant to be overridden in child classes if
        needed"""
        return kwargs.get("reader_row_class", CSVRow)(
            columns,
            self.lookup
        )

#     def normalize_reader_row(self, row):
#         """prepare row for reading, meant to be overridden in child classes if
#         needed"""
#         if not self.strict:
#             # we're checking for a None key, which means there were extra
#             # commas
#             if None in row and not any(row.get(None, [])):
#                 # the CSV file has extra commas at the end of the row, this is 
#                 # pretty common with simple auto csv generators that just put a
#                 # comma at the end of each column value when outputting the row
#                 row.pop(None, None)
# 
#         if self.reader_row_class:
#             row = self.reader_row_class(row)
# 
#         return row

    def create_writer_row(self, row, **kwargs):
        """prepare row for writing, meant to be overridden in child classes if
        needed
        """
        if writer_row_class := kwargs.get("writer_row_class", None):
            row = writer_row_class(row, self.lookup)

        else:
            def get_value(v):
                if self.strict:
                    return ByteString(v)

                else:
                    # NOTE -- for some reason, the internal writer treats b"" and
                    # ByteString(b"") differently, the b"" would be written out as
                    # "b""" which make me think it's doing repr(value) internally
                    # or something
                    return ByteString(b"" if v is None else v)

            row = {
                String(k): get_value(v) for k, v in row.items()
            }

            if self.strict:
                rowcount = len(row)
                fncount = len(self.fieldnames)
                if rowcount != fncount:
                    raise ValueError(
                        "mismatch {} row(s) to {} fieldname(s)".format(
                            rowcount,
                            fncount
                        )
                    )

        return row


#     def normalize_writer_row(self, row):
#         """prepare row for writing, meant to be overridden in child classes if
#         needed
#         """
#         row = {
#             String(k): self.normalize_writer_value(v) for k, v in row.items()
#         }
# 
#         if self.strict:
#             rowcount = len(row)
#             fncount = len(self.fieldnames)
#             if rowcount != fncount:
#                 raise ValueError(
#                     "mismatch {} row(s) to {} fieldname(s)".format(
#                         rowcount,
#                         fncount
#                     )
#                 )
# 
#         if self.writer_row_class:
#             row = self.writer_row_class(row)
# 
#         return row

#     def normalize_writer_value(self, value):
#         """Ran for each individual value in a row
# 
#         see .normalize_writer_row because if you overwrite that method in a
#         child class then this might not be called
# 
#         :param value: Any
#         :returns: bytes
#         """
#         if self.strict:
#             return ByteString(value)
# 
#         else:
#             # NOTE -- for some reason, the internal writer treats b"" and
#             # ByteString(b"") differently, the b"" would be written out as
#             # "b""" which make me think it's doing repr(value) internally or
#             # something
#             return ByteString(b"" if value is None else value)

#     def normalize_writer_fieldnames(self, fieldnames):
#         """run this right before setting fieldnames onto the writer instance
#         """
#         return fieldnames
# 
#     def normalize_reader_fieldnames(self, fieldnames):
#         """run this right before setting fieldnames onto the reader instance
#         """
#         return fieldnames

#     def normalize_fieldnames(self, fieldnames):
#         """run this anytime fields are going to be set on this instance"""
#         return list(map(String, fieldnames)) if fieldnames else []

    def set_fieldnames(self, fieldnames):
        if fieldnames:
            self.fieldnames = list(map(String, fieldnames))
            #self.lookup = {item[0]: item[1] for item in enumerate(fieldnames)}
            self.lookup = {item[1]: item[0] for item in enumerate(fieldnames)}

        else:
            self.fieldnames = []
            self.lookup = {}

    def find_fieldnames(self):
        """attempt to get the field names from the first line in the csv file
        """
        if self.fieldnames:
            return self.fieldnames

        else:
            for row in self:
                return self.fieldnames

#         with self.reading() as f:
#             reader = self.create_reader(f)
#             return list(map(String, reader.fieldnames))

    def rows(self):
        """Return all the rows as a list"""
        return self.tolist()

    def tolist(self):
        """Return all the rows as a list

        Here for consistent interface as I'm using .tolist elsewhere

        :returns: list
        """
        return list(self.__iter__())

    def clear(self):
        """clear the csv file"""
        with self.writing() as stream:
            stream.truncate(0)

    def __iter__(self):
        with self.reading() as stream:
            ignore_row = True
            reader = self.create_reader(stream)
            for columns in reader:
                if ignore_row:
                    if self.fieldnames:
                        # if you've passed in fieldnames then it will
                        # return fieldnames mapped to fieldnames as the
                        # first row, this will catch that and ignore it
                        #
                        # if we pass in fieldnames then DictReader won't
                        # use the first row as fieldnames, so we need to
                        # check to make sure the first row isn't a
                        # field_name: field_name mapping
                        for i, col in enumerate(columns):
                            if self.fieldnames[i] != col:
                                ignore_row = False
                                break

                    else:
                        # if we don't have field names then the first row
                        # has to be the fieldnames
                        self.set_fieldnames(columns)

                if not ignore_row:
                    ignore_row = False
                    row = self.create_reader_row(columns)
                    if row is not None:
                        yield row

    def __len__(self):
        """Returns how many rows are in this csv, this actually goes through
        all the rows, so this is not a resource light method"""
        count = 0
        for r in self:
            count += 1
        return count

    def __str__(self):
        return self.read_text()

    def read_text(self):
        """This will print out all rows so it might not be ideal to use for 
        bigger CSVs"""
        with self.reading() as stream:
            return stream.read()


class TempCSV(CSV):
    def __init__(self, fieldnames=None, **kwargs):
        path = TempFilepath(kwargs.pop("path", ""), dir=kwargs.pop("dir", ""))
        kwargs["fieldnames"] = fieldnames
        super().__init__(path, **kwargs)

