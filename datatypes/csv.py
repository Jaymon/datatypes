# -*- coding: utf-8 -*-
import csv
from contextlib import contextmanager
import io

from .compat import *
from .config.environ import environ
from .string import String, ByteString
from .path import TempFilepath, Filepath
from . import logging


logger = logging.getLogger(__name__)


class CSVRowDict(dict):
    """An actual dict for each row

    While this is about 50% slower than CSVRow, sometimes, like trying to
    serialize a CSV row using orjson, you need an actual dict and not
    something that just quacks like a dict. Basically, anything that is
    using the Python C api PyDict_Next won't be able to "see" the CSVRow's
    actual data so you have to take the speed hit and use something like
    this class

    .. Example:
        # use a custom CSV row class
        c = CSV("<CSV-PATH>", reader_row_class=CSVRowDict)
        for row in c:
            assert isinstance(row, dict)
    """
    def __init__(self, columns, lookup):
        super().__init__(zip(lookup.keys(), columns))


class CSVRow(Mapping):
    """By default the CSV reader will return an instance of this class

    This is done in `CSV.create_reader_row`. This exists because
    csv.DictReader was quite a bit slower than expected in real world use,
    using this sped up CSV reading by about 2.5-3x.

    This walks and talks like a dict but it is not a traditional dict, that's
    something to be aware of.

    There is a bit of overhead for creating these instances, so if the most
    performance is a necessity, you can override `CSV.create_reader_row` and
    just return the columns, then you can manually grab columns using the
    CSV instance's `.lookup` property exactly how this class does it

    `Mapping` parent gives implementations for .__contains__, .items, .keys,
    and .values

    https://github.com/python/cpython/blob/3.11/Lib/_collections_abc.py#L754
    """
    def __init__(self, columns, lookup):
        """
        :param columns: list, the list of values of this row
        :param lookup: dict[str, int], the keys are the field names and the
            values are the index in `columns` of the value that corresponds
            to that field name
        """
        self.columns = columns
        self.lookup = lookup
        self.mutable = False

    def _make_mutable(self):
        """Converts this row into a mutable row

        If we're adding or removing fields then we need a local copy of
        .lookup so we don't mess up any other rows in the CSV
        """
        if not self.mutable:
            self.lookup = {**self.lookup}
            self.mutable = True

    def __getitem__(self, k):
        return self.columns[self.lookup[k]]

    def __setitem__(self, k, v):
        """the value of .columns is updated with v if it already exists,
        otherwise v is added to the end of .columns"""
        if k in self.lookup:
            self.columns[self.lookup[k]] = v

        else:
            self._make_mutable()
            self.lookup[k] = len(self.columns)
            self.columns.append(v)

    def __delitem__(self, k):
        """This just sets the field's value in .columns to None and removes k
        from .lookup"""
        self._make_mutable()
        i = self.lookup.pop(k)
        self.columns[i] = None

    def __iter__(self):
        yield from self.lookup

    def __len__(self):
        return len(self.lookup)

    def pop(self, k, *default):
        try:
            v = self[k]
            del self[k]

        except KeyError:
            if default:
                v = default[0]

            else:
                raise

        return v

#     def __contains__(self, k):
#         return k in self.lookup
# 
#     def get(self, k, default=None):
#         try:
#             return self[k]
# 
#         except (KeyError, IndexError):
#             return default

    def popitem(self):
        self._make_mutable()
        k, i = self.lookup.popitem()
        v = self.columns[i]
        self.columns[i] = None
        return k, v

    def clear(self):
        self._make_mutable()
        self.lookup.clear()
        self.columns = []

    def __reversed__(self):
        return reversed(list(self.keys()))

    def copy(self):
        return type(self)(self.columns, self.lookup)

    def setdefault(self, k, v):
        if k not in self:
            self[k] = v

    def update(self, *others, **kwargs):
        for other in others:
            if keys := getattr(other, "keys", None):
                for k in keys():
                    self[k] = other[k]

            else:
                for k, v in other:
                    self[k] = v

        for k, v in kwargs.items():
            self[k] = v

    def __or__(self, other):
        r = self.copy()
        r.update(other)
        return r

    def __ior__(self, other):
        self.update(other)
        return self


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

    In testing, this is about 25-30% slower than the vanilla CSV reader but
    gives you dict support among other niceties

    https://docs.python.org/3/library/csv.html
    """
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
            write_mode: str, the default mode that will be passed to open a
                stream for writing
            readonly: bool, True if writing operations should fail
        """
        self.path = path
        self.set_fieldnames(fieldnames)
        self.writer = None
        self.reader = None
        self.strict = kwargs.pop("strict", False)

        self.readonly = kwargs.pop("readonly", False)
        if self.readonly:
            self.write_mode = kwargs.pop("write_mode", "")
            self.append_mode = kwargs.pop("append_mode", "")

        else:
            self.write_mode = kwargs.pop("write_mode", "w+")
            self.append_mode = kwargs.pop("append_mode", "a+")

        if not encoding:
            encoding = environ.ENCODING
        self.encoding = encoding

        self.reader_row_class = kwargs.get("reader_row_class", CSVRow)
        self.writer_row_class = kwargs.get("writer_row_class", None)
        self.writer_class = kwargs.get("writer_class", csv.DictWriter)
        self.reader_class = kwargs.get("reader_class", csv.reader)

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
            with self.open(self.write_mode) as stream:
                yield stream

    @contextmanager
    def appending(self):
        """The default context manager truncates and write a new file, but that
        doesn't work for .add(), .append(), or .extend() so this provides an
        alternative context manager for appending to the file
        """
        prev_mode = self.write_mode
        self.write_mode = self.append_mode
        try:
            with self:
                yield self

        finally:
            self.write_mode = prev_mode

    def __enter__(self):
        """Enables with context manager for writing"""
        if not self.writer:
            cm = self.writing()
            self.writer = self.create_writer(cm.__enter__())
            self.writer.cm = cm
            # protection against multiple context managers
            self.writer.context_depth = 0

        self.writer.context_depth += 1
        return self

    def __exit__(self, exc_class, exc, trace):
        self.writer.context_depth -= 1
        if self.writer.context_depth <= 0:
            self.writer.cm.__exit__(exc_class, exc, trace)
            self.writer = None

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

        writer = kwargs.pop("writer_class", self.writer_class)(
            stream,
            **kwargs
        )
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
        reader = kwargs.pop("reader_class", self.reader_class)(
            stream,
            **kwargs
        )
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

                    writer.fieldnames = self.fieldnames
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

    def create_reader_row(self, columns, **kwargs):
        """prepare row for reading, meant to be overridden in child classes if
        needed"""
        #return {k: columns[self.lookup[k]] for k in self.lookup}
        return kwargs.get("reader_row_class", self.reader_row_class)(
            columns,
            self.lookup
        )

    def create_writer_row(self, row, **kwargs):
        """prepare row for writing, meant to be overridden in child classes if
        needed
        """
        writer_row_class = kwargs.get(
            "writer_row_class",
            self.writer_row_class
        )
        if writer_row_class:
            row = writer_row_class(row, self.lookup)

        else:
            def get_value(v):
                if self.strict:
                    return ByteString(v)

                else:
                    # NOTE -- for some reason, the internal writer treats b""
                    # and ByteString(b"") differently, the b"" would be written
                    # out as "b""" which make me think it's doing repr(value)
                    # internally or something
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

    def set_fieldnames(self, fieldnames):
        """Set the fieldnames and create the lookup table

        :param fieldnames: list[str], a list of fieldnames that corresponds
            to the columns in the CSV file
        """
        if fieldnames:
            self.fieldnames = list(map(String, fieldnames))
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
                        # Check to see if the fieldnames are the first row of
                        # the CSV file, if they are then ignore this row
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
    """Create a temporary CSV file in the system's tempdir"""
    def __init__(self, fieldnames=None, **kwargs):
        path = TempFilepath(kwargs.pop("path", ""), dir=kwargs.pop("dir", ""))
        kwargs["fieldnames"] = fieldnames
        super().__init__(path, **kwargs)

