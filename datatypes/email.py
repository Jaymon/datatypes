import re
import os
import mimetypes
import time
from collections import defaultdict
import email.utils
from email.parser import Parser, BytesParser
from email.header import decode_header
from email.message import EmailMessage
from typing import Self
from functools import cached_property
import io

from .compat import *
from .config.environ import environ
from .string import String, ByteString
from .datetime import Datetime
from .path import Filepath, Dirpath
from .http import HTTPHeaders


def get_decoded_header(data: str|bytes) -> str:
    """Helper function. This puts all the pieces of a decoded header together
    into a string"""
    ds = decode_header(data)
    data = ""
    for d, encoding in ds:
        if isinstance(d, str):
            data += d

        else:
            if encoding:
                data += d.decode(encoding)

            else:
                data += d.decode()

    return data


class EmailAddress(str):
    """The parts of an email address header

    `<name> <username@subdomain.domain>`
    """
    name: str = ""
    """Holds the name section of an email address"""

    @cached_property
    def username(self) -> str:
        return self.split("@", 1)[0]

    @cached_property
    def domain(self) -> str:
        return self.split("@", 1)[1]

    @property
    def hostname(self) -> str:
        return self.domain

    @cached_property
    def address(self) -> str:
        return str(self)

    def __new__(cls, address: str|tuple[str, str]) -> Self:
        if address:
            if isinstance(address, str):
                address = email.utils.parseaddr(address)

        else:
            address = ("", "")

        name, address = address
        name = get_decoded_header(name)

        instance = super().__new__(cls, address)
        instance.name = name
        return instance

    def formataddr(self) -> str:
        """Formats the address for an email header, wrapper around
        `email.utils.formataddr`

        https://docs.python.org/3/library/email.utils.html#email.utils.formataddr
        """
        return email.utils.formataddr((self.name, self))

    def parseaddr(self) -> tuple[str, str]:
        """Acts just like `email.utils.parseaddr`
        https://docs.python.org/3/library/email.utils.html#email.utils.parseaddr
        """
        return (self.name, self.address)


class EmailPart(object):
    """Represents one part of a multipart email

    this class probably isn't useful outside of the Email class in this module
    """
    def __init__(
        self,
        email: "Email",
        content_type: str,
        data: bytes,
        encoding: str,
        encodings: list[str]|None = None,
        errors: str = "strict",
        filename: str = "",
        index: int = 1,
    ):
        """
        :param email: Email, the full email instance
        :param content_type: str, the mimetype of the part
        :param data: the part's data/body
        :param encoding: str, the content encoding
        :param encodings: list[str], the fallback encodings if encoding fails
        :param errors: str, how to handle encoding errors. Defaults to
            "strict" but can be "ignore" or "replace"
        :param filename: str, filename for this attachment, if not provided
            this part will be considered a body instead of an attachment
        :param index: int, the part index/num of this email
        """
        self.email = email
        self.content_type = content_type
        self.filename = filename
        self.index = index

        if self.filename:
            # don't mess with the data since this will be treated like a
            # binary file
            self.data = data

        else:
            if not encodings:
                encodings = []

            if encoding:
                encodings = [encoding, *encodings]

            enc_errors = []

            for enc in encodings:
                if enc:
                    try:
                        self.data = data.decode(enc, errors=errors)
                        self.encoding = enc
                        enc_errors = []
                        break

                    except (UnicodeDecodeError, LookupError) as e:
                        # LookupError for unknown encoding codec
                        # UnicodeDecodeError for improper encoding codec
                        enc_errors.append(e)

            if enc_errors:
                raise UnicodeDecodeError(
                    encoding,
                    data,
                    0,
                    len(data),
                    "Unable to decode data with encodings: {}".format(
                        ", ".join(encodings),
                    ),
                ) from ExceptionGroup("Found encoding errors", enc_errors)

    def path(self, basedir):
        """Get the save path for this part

        :param basedir: string, the base directory this will use to generate a
            full path
        :returns: string, the full path to a file that this part could be
            saved to
        """
        if self.filename:
            fileroot, ext = os.path.splitext(self.filename)

        else:
            content_type = self.content_type
            fileroot = f"body {self.index}"
            if content_type.endswith("plain"):
                ext = ".txt"

            else:
                ext = mimetypes.guess_extension(self.content_type, False)
                if not ext:
                    ext = ".txt"

        return Filepath(basedir, name=fileroot, ext=ext).sanitize()

    def save(self, basedir):
        '''Method to save the data of an attachment to a file
        arguments:

        :param basedir: string, directory path where file is to be saved
        :returns: Path, the written filepath saved in basedir
        '''
        if not self.data: return

        p = self.path(basedir)
        if self.filename:
            p.write_bytes(self.data)

        else:
            p.write_text(self.data)

        return p

    def is_attachment(self) -> bool:
        """True if this is an attachment, False if it is a body"""
        return bool(self.filename)

    def is_body(self) -> bool:
        """True if this is a body, False if it is an attachment"""
        return not self.is_attachment()


class Email(object):
    """Allow programmatic access to a raw email

    This was ripped out of popbak in December 2021 and plopped here

    The original email parsing portion of the code was based on code that I got
    from Larry Bates here:
        http://mail.python.org/pipermail/python-list/2004-June/265634.html

    https://en.wikipedia.org/wiki/Email_address
    """
    part_class = EmailPart
    """Each body or attachment in the email will be represented by this class"""

    @property
    def raw(self): # DEPRECATED
        return String(self.msg)

    @cached_property
    def headers(self) -> HTTPHeaders:
        return HTTPHeaders(self.msg.items())

    @cached_property
    def subject(self) -> str:
        if ret := self.msg.get("Subject", ""):
            # https://stackoverflow.com/a/7331577/5006
            ret = get_decoded_header(ret)

        return ret

    @cached_property
    def references(self) -> list[str]:
        header_values = self.msg.get_all("References", [])
        if not header_values:
            header_values = self.msg.get_all("In-Reply-To", [])


        refs = []
        if header_values:
            for hv in header_values:
                refs.extend(re.split(r"\s+", hv))

        return refs

    @cached_property
    def msgid(self) -> str:
        """Return a unique msgid for this email

        If a msgid isn't found in the headers then one will be created, so
        this will always return something

        Returns a msgid that is similar to one returned from
        `email.utils.make_msgid`
        """
        msgid = self.msg.get("Message-ID", "")
        if not msgid:
            addr = self.reply_address
            h = String(self.msg).sha256()
            msgid = f"<{h}@{addr.domain}>"

        return msgid

    @cached_property
    def addresses(self) -> list[EmailAddress]:
        """Return all the email addresses involved in the email, this is all
        the email addresses of recipients and senders"""
        header_values = []
        header_names = [
            "From",
            "Sender",
            "To",
            "Cc",
            "Bcc",
            "Reply-To",
            "Resent-From",
            "Resent-Sender",
            "Resent-To",
            "Resent-Cc",
            "Resent-Bcc",
            "Return-Path",
            "Delivered-To",
        ]

        for header_name in header_names:
            header_values.extend(self.msg.get_all(header_name, []))

        addrs = []
        seen = set()
        for name, email_address in email.utils.getaddresses(header_values):
            if email_address not in seen:
                addrs.append(EmailAddress((name, email_address)))
                seen.add(email_address)

        return addrs

    @cached_property
    def recipient_addresses(self) -> list[EmailAddress]:
        """return all the recipient email addresses

        https://docs.python.org/3/library/email.util.html#email.utils.getaddresses

        :returns: list, the list of recipients, this includes to, cc, bcc, etc.
        """
        tos = self.msg.get_all("to", [])
        ccs = self.msg.get_all("cc", [])
        bccs = self.msg.get_all("bcc", [])
        resent_tos = self.msg.get_all("resent-to", [])
        resent_ccs = self.msg.get_all("resent-cc", [])
        recipient_addrs = email.utils.getaddresses(
            tos + bccs + ccs + resent_tos + resent_ccs
        )
        return [EmailAddress(a) for a in recipient_addrs if a[1]]

    @property
    def recipient_addrs(self): # DEPRECATED
        return self.recipient_addresses

    @cached_property
    def to_address(self) -> EmailAddress:
        """Return the address that the email was delivered to, if that address
        can't be inferred then return an empty string
        """
        to_addrs = self.msg.get_all("Delivered-To", [])
        if not to_addrs:
            to_addrs = self.msg.get_all("To", [])

        if len(to_addrs) == 1:
            return EmailAddress(email.utils.getaddresses(to_addrs)[0])

        return EmailAddress("")

    @cached_property
    def to_addresses(self) -> list[EmailAddress]:
        """Only to addresses, ignore cc"""
        to_addrs = email.utils.getaddresses(self.msg.get_all("To", []))
        to_addrs = [EmailAddress(a) for a in to_addrs]
        return to_addrs

    @property
    def to_addrs(self): # DEPRECATED
        return self.to_addresses

    @cached_property
    def from_address(self) -> EmailAddress:
        """Get just the email address this email is from"""
        from_addr = ""
        from_addrs = email.utils.getaddresses(self.msg.get_all("From", []))
        return EmailAddress(from_addrs[0] if from_addrs else "")

    @property
    def from_addr(self): # DEPRECATED
        return self.from_address

    @cached_property
    def reply_address(self) -> EmailAddress:
        """The email address that should be used to reply to this email"""
        addrs = self.msg.get_all("Reply-To", [])
        if not addrs:
            addrs = self.msg.get_all("From", [])

        return EmailAddress(email.utils.getaddresses(addrs)[0])

    @property
    def from_domain(self) -> str:
        """Get the from email address domain (eg, the example.com of a
        foo@example.com email address)"""
        addr = self.from_addr
        return addr.domain

    @property
    def date(self) -> str: # DEPRECATED
        """Get the string datestamp from the email"""
        ret = str(self.msg.get('Date', ""))
        return ret

    @cached_property
    def datetime(self) -> Datetime|None:
        """Convert .date into a datetime instance

        :returns: Datetime|None, if the date header exists this will return
            a datetime instance with the date the email was sent, if no date
            header is found then this will return None
        """
        d = self.msg.get('Date', "")
        #d = self.date
        if d:
            # https://docs.python.org/3/library/email.util.html#email.utils.parsedate_tz
            t = email.utils.parsedate_tz(d)
            stamp = time.mktime(t[0:9])

            # we want to convert this to UTC
            tz_offset = t[9]
            if tz_offset:
                stamp -= tz_offset

            return Datetime(stamp)

    @property
    def plain(self):
        """Return the plain text body of this email"""
        ret = self.parts["text/plain"]
        return ret[0].data

    @property
    def html(self):
        """Return the html body of this email, if it exists"""
        ret = self.parts.get("text/html", [])
        ret = ret[0].data if ret else ""
        return ret

    def __init__(
        self,
        data: bytes|str|io.IOBase|EmailMessage,
        encodings: list[str]|None = None,
        errors: str = "strict",
    ):
        """Encapsulate a raw/original email message

        :param data: an original full email with all headers and parts
        :param encodings: list[str], the fallback encodings if the header
            defined encoding fails, this defaults to a list of the most common
            email encodings, the first encoding that succeeds will be used
        :param errors: str, how to handle encoding errors. Passing in "ignore"
            will make the email parser ignore encoding errors. See String for
            how errors is used and what the default is and how to change the
            default
        """
        self.data = data
        self.parts = defaultdict(list)

        if encodings is None:
            encodings = ["UTF-8", "ISO-8859-1", "us-ascii"]

        if isinstance(data, bytes):
            self.msg = BytesParser().parsebytes(data)

        elif isinstance(data, str):
            self.msg = Parser().parsestr(data)

        elif isinstance(data, io.IOBase):
            mode = getattr(data, "mode", "")
            if isinstance(data, io.BufferedIOBase) or "b" in mode:
                self.msg = BytesParser().parse(data)

            else:
                # Treat all other io as text io and pray
                self.msg = Parser().parse(data)

        elif isinstance(data, EmailMessage):
            self.msg = data

        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        if self.msg.is_multipart():
            index = 0
            for part in self.msg.walk():
                # multipart/* are just containers
                if part.is_multipart():
                    continue

                content_type = part.get_content_type()
                encoding = part.get_content_charset()
                filename = part.get_filename()
                part_data = part.get_payload(decode=True)
                index += 1

                self.parts[content_type].append(self.part_class(
                    email=self,
                    content_type=content_type,
                    data=part_data,
                    encoding=encoding,
                    encodings=encodings,
                    errors=errors,
                    filename=filename,
                    index=index,
                ))

        else: # Not multipart, only body portion exists

            # RFC 2045 defines a message’s default type to be text/plain unless
            # it appears inside a multipart/digest container, in which case it
            # would be message/rfc822
            content_type = self.msg.get_content_type()
            encoding = self.msg.get_content_charset()
            part_data = self.msg.get_payload(decode=1)
            self.parts[content_type].append(self.part_class(
                email=self,
                content_type=content_type,
                data=part_data,
                encoding=encoding,
                encodings=encodings,
                errors=errors,
            ))

    def path(self, basedir):
        """Get the save path for this email, this should be a directory that
        all the parts can be saved into

        :param basedir: string, the base directory that will be used to
            generate a full path
        :returns: string, the full path to a directory this email can be saved
            into
        """
        stamp = self.datestamp("%Y-%m-%d %H%M%S")
        subject = self.subject or "(no subject)"

        s = f"{stamp} - {self.subject}"

        # remove path delims from the subject
        s = re.sub(r"[\\/]+", " ", s)

        return Dirpath(
            basedir,
            f"{self.from_domain}",
            f"{self.from_addr}/{s}",
        ).sanitize(maxpath=220)

    def paths(self, basedir):
        """Returns all the potential paths that .save() could use. This is
        really more for debugging because it might generate different paths
        since it doesn't actually create the paths, which might cause datatypes
        Path.sanitize() to produce different results

        :param basedir: string, the base directory that will be used to generate
            a full path
        :returns: list, all the folders and attachment/bpdy paths this could
            generate
        """
        email_dir = self.path(basedir)
        paths = [email_dir]
        for ps in self.parts.values():
            for p in ps:
                paths.append(p.path(email_dir))
        return paths

    def bodies(self):
        """Get all the bodies in the email"""
        for ps in self.parts.values():
            for b in ps:
                if b.is_body():
                    yield b

    def attachments(self):
        """Get all the attachments of the email"""
        for ps in self.parts.values():
            for a in ps:
                if a.is_attachment():
                    yield a

    def has_attachments(self) -> bool:
        """Does this email have attachments? Returns True or False"""
        for a in self.attachments():
            return True
        return False

    def has_attachment(self) -> bool:
        """Alias of .has_attachments()"""
        return self.has_attachments()

    def datestamp(self, strformat="", default="UNKNOWN"):
        """Get a datestamp for the email using strformat, if the email doesn't
        have a date header than use the default

        :param strformat: str, same thing you would pass to strftime or
            strptime, it will default to ISO format if empty.
            https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
        :param default: str, what the default value should be if there is no
            date header
        :returns: str, the date stamp
        """
        stamp = default

        dt = self.datetime
        if dt:
            if strformat:
                stamp = self.datetime.strftime(strformat)

            else:
                stamp = dt.isoformat()

        return stamp

    def save(self, basedir, save_original=False):
        """Save this email into basedir

        this will generate a base email path in the format:

            basedir/<FROM_DOMAIN>/<FROM_ADDR>/<DATE> - <SUBJECT>

        Then it will use this base email path to save all the headers, bodies,
        and attachments of the email

        :param basedir: string, path to save the email into
        :param save_original: bool, True if you would also like to save the full
            original email in original.eml.
            eml: https://www.loc.gov/preservation/digital/formats/fdd/fdd000388.shtml
        :returns: list, all the paths the email saved
        """
        ret = []
        email_dir = self.path(basedir)
        email_dir.touch()

        if save_original:
            p = Filepath(email_dir, "original.eml")
            p.write_bytes(bytes(self))
            ret.append(p)

        ret.append(email_dir)
        for ps in self.parts.values():
            for p in ps:
                rp = p.save(email_dir)
                if rp:
                    ret.append(rp)

        p = Filepath(email_dir, "headers.txt")
        with p.open_text("w+") as f:
            f.write("From:\n\t- {}\n".format(self.from_address))
            f.write("Recipients:\n\t- {}\n".format(
                "\n\t- ".join(self.recipient_addresses)
            ))
            f.write("Subject: {}\n".format(self.subject))
            f.write("Date: {}\n\n".format(self.datestamp()))

            f.write(str(self.headers))

        ret.append(p)

        return ret

    def __str__(self) -> str:
        return str(self.msg)

    def __bytes__(self) -> bytes:
        return bytes(self.msg)

