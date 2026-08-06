import re
import os
import mimetypes
import time
from collections.abc import Generator
from email.parser import Parser, BytesParser
from email import message, policy, utils, parser, header
from typing import Self
from functools import cached_property
import io

from .compat import *
from .string import String
from .datetime import Datetime
from .path import Filepath, Dirpath
from .http import HTTPHeaders


def get_decoded_header(data: str|bytes) -> str:
    """Helper function. This puts all the pieces of a decoded header together
    into a string"""
    ds = header.decode_header(data)
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

    `name <username@domain>`
           \_____________/
                  |
               address

    :example:
        addr = EmailAddress("Foo Bar <foo@bar.com>") 
        print(addr) # "foo@bar.com"
        print(addr.name) # "Foo Bar"
        print(addr.formataddr()) # "Foo Bar <foo@bar.com>"
        print(addr.parseaddr()) # ("Foo Bar", "foo@bar.com")
    """
    name: str = ""
    """Holds the name section of an email address"""

    @cached_property
    def username(self) -> str:
        """Return `username` segment of `<name> <username@domain>`"""
        return self.split("@", 1)[0]

    @cached_property
    def domain(self) -> str:
        """Return `domain` segment of `<name> <username@domain>`"""
        return self.split("@", 1)[1]

    @property
    def hostname(self) -> str:
        """Alias for `.domain`"""
        return self.domain

    @cached_property
    def address(self) -> str:
        """Return `username@domain` segment of `<name> <username@domain>`"""
        return str(self)

    def __new__(cls, address: str|tuple[str, str]) -> Self:
        if address:
            if isinstance(address, str):
                address = utils.parseaddr(address)

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
        return utils.formataddr((self.name, self))

    def parseaddr(self) -> tuple[str, str]:
        """Acts just like `email.utils.parseaddr`
        https://docs.python.org/3/library/email.utils.html#email.utils.parseaddr
        """
        return (self.name, self.address)


class EmailMessage(message.EmailMessage):
    """This is a drop in replacement for the stdlib `email.message.Message`

    You can use this as a drop in replacement when parsing emails

    :example:
        import email
        from datatypes import EmailMessage

        # use this class when parsing
        s = "<RAW EMAIL>"
        m = email.message_from_string(s, _class=EmailMessage)
        print(type(m)) # datatypes.email.EmailMessage

    https://docs.python.org/3/library/email.message.html#email.message.EmailMessage
    """
    @property
    def headers(self) -> HTTPHeaders:
        """Return all the headers of this email"""
        return HTTPHeaders(self.items())

    @property
    def subject(self) -> str:
        """Return the subject header value"""
        return self.get_subject("")

    @property
    def references(self) -> list[str]:
        """All the previous emails message ids this email references"""
        header_values = self.get_all("References", [])
        if not header_values:
            header_values = self.get_all("In-Reply-To", [])


        refs = []
        if header_values:
            for hv in header_values:
                refs.extend(re.split(r"\s+", hv))

        return refs

    @property
    def msgid(self) -> str:
        """Return a unique msgid for this email

        If a msgid isn't found in the headers then one will be created, so
        this will always return something

        Returns a msgid that is similar to one returned from
        `email.utils.make_msgid`
        """
        msgid = self.get("Message-ID", "")
        if not msgid:
            addr = self.reply_address
            h = String(self).sha256()
            msgid = f"<{h}@{addr.domain}>"

        return msgid

    @property
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
            header_values.extend(self.get_all(header_name, []))

        addrs = []
        seen = set()
        for name, email_address in utils.getaddresses(header_values):
            if email_address not in seen:
                addrs.append(EmailAddress((name, email_address)))
                seen.add(email_address)

        return addrs

    @property
    def recipient_addresses(self) -> list[EmailAddress]:
        """return all the recipient email addresses

        https://docs.python.org/3/library/email.util.html#email.utils.getaddresses

        :returns: the list of recipients, this includes to, cc, bcc, etc.
        """
        tos = self.get_all("to", [])
        ccs = self.get_all("cc", [])
        bccs = self.get_all("bcc", [])
        resent_tos = self.get_all("resent-to", [])
        resent_ccs = self.get_all("resent-cc", [])
        recipient_addrs = utils.getaddresses(
            tos + bccs + ccs + resent_tos + resent_ccs
        )
        return [EmailAddress(a) for a in recipient_addrs if a[1]]

    @property
    def to_address(self) -> EmailAddress:
        """Return the address that the email was delivered to, if that address
        can't be inferred then return an empty string
        """
        to_addrs = self.get_all("Delivered-To", [])
        if not to_addrs:
            to_addrs = self.get_all("To", [])

        if len(to_addrs) == 1:
            return EmailAddress(utils.getaddresses(to_addrs)[0])

        return EmailAddress("")

    @property
    def to_addresses(self) -> list[EmailAddress]:
        """Only to addresses, ignore cc"""
        to_addrs = utils.getaddresses(self.get_all("To", []))
        to_addrs = [EmailAddress(a) for a in to_addrs]
        return to_addrs

    @property
    def from_address(self) -> EmailAddress:
        """Get just the email address this email is from"""
        from_addr = ""
        from_addrs = utils.getaddresses(self.get_all("From", []))
        return EmailAddress(from_addrs[0] if from_addrs else "")

    @property
    def reply_address(self) -> EmailAddress:
        """The email address that should be used to reply to this email"""
        addrs = self.get_all("Reply-To", [])
        if not addrs:
            addrs = self.get_all("From", [])

        return EmailAddress(utils.getaddresses(addrs)[0])

    @property
    def from_domain(self) -> str:
        """Get the from email address domain (eg, the example.com of a
        foo@example.com email address)"""
        addr = self.from_address
        return addr.domain

    @property
    def datetime(self) -> Datetime|None:
        """Convert the `Date` header into a datetime instance

        :returns: Datetime|None, if the `date` header exists this will return
            a datetime instance with the date the email was sent, if no date
            header is found then this will return None
        """
        d = self.get("Date", "")
        if d:
            # https://docs.python.org/3/library/email.util.html#email.utils.parsedate_tz
            t = utils.parsedate_tz(d)
            stamp = time.mktime(t[0:9])

            # we want to convert this to UTC
            tz_offset = t[9]
            if tz_offset:
                stamp -= tz_offset

            return Datetime(stamp)

    def datestamp(self, strformat: str = "", default: str = "UNKNOWN") -> str:
        """Get a datestamp for the email using strformat, if the email doesn't
        have a date header than use the default

        :param strformat: same thing you would pass to strftime or
            strptime, it will default to ISO format if empty.
            https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
        :param default: what the default value should be if there is no
            date header
        :returns: the date stamp
        """
        stamp = default

        dt = self.datetime
        if dt:
            if strformat:
                stamp = self.datetime.strftime(strformat)

            else:
                stamp = dt.isoformat()

        return stamp

    def is_attachment(self) -> bool:
        """True if this is an attachment, False if it is a body"""
        return bool(self.get_filename())

    def is_body(self) -> bool:
        """True if this is a body, False if it is an attachment"""
        return not self.is_attachment()

    def walk_content(self) -> Generator[message.Message]:
        """Recursively walk all the parts that actually contain content.

        This will basically yield all attachments and email bodies that
        contain text (eg, text/plain and text/html)
        """
        for p in self.walk():
            if not p.is_multipart():
                yield p

    def walk_bodies(self) -> Generator[message.Message]:
        """Get all the bodies in the email"""
        for p in self.walk_content():
            if p.is_body():
                yield b

    def walk_attachments(self) -> Generator[message.Message]:
        """Get all the attachments of the email"""
        for p in self.walk_content():
            if p.is_attachment():
                yield p

    def has_attachments(self) -> bool:
        """Does this email have attachments? Returns True or False"""
        for a in self.walk_attachments():
            return True
        return False

    def has_attachment(self) -> bool:
        """Alias of .has_attachments()"""
        return self.has_attachments()

    def get_subject(self, default: str = "") -> str:
        """Return the email's subject, defaulting to `default` if no subject
        header is found or subject is empty"""
        if ret := self.get("Subject", ""):
            # https://stackoverflow.com/a/7331577/5006
            ret = get_decoded_header(ret)

        else:
            ret = default

        return ret

    def get_part(self, content_type: str) -> message.Message:
        """Return the first part matching `content_type`

        :param content_type: values like `text/html` or `text/plain`
        """
        for p in self.walk():
            if p.get_content_type() == content_type:
                return p


class Email(EmailMessage):
    """A wrapper around stdlib's email parsing. I just like being able to
    pass my raw email into the init method and have everything parsed.

    If you want to use the built-in parsing, you can just pass `EmailMessage`
    into the stdlib parsing function/class
    """
    @property
    def plain(self) -> str:
        """Return the first plain text body of this email, if it exists"""
        p = self.get_body(("plain",))
        return p.get_content() if p else ""

    @property
    def html(self) -> str:
        """Return the first html body of this email, if it exists"""
        p = self.get_body(("html",))
        return p.get_content() if p else ""

    def __init__(
        self,
        data: bytes|str|io.IOBase|message.Message|None = None,
        _class: type[message.Message] = EmailMessage,
    ):
        """Encapsulate a raw/original email message

        :param data: an original full email with all headers and parts
        """
        if data is not None:
            super().__init__()

            parser_kwargs = {
                "_class": _class,
                "policy": self.policy,
            }

            if isinstance(data, message.Message):
                em = data

            elif isinstance(data, bytes):
                em = parser.BytesParser(**parser_kwargs).parsebytes(data)

            elif isinstance(data, str):
                em = parser.Parser(**parser_kwargs).parsestr(data)

            elif isinstance(data, io.IOBase):
                mode = getattr(data, "mode", "")
                if isinstance(data, io.BufferedIOBase) or "b" in mode:
                    em = parser.BytesParser(**parser_kwargs).parse(data)

                else:
                    # Treat all other io as text io and pray
                    em = parser.Parser(**parser_kwargs).parse(data)

            else:
                raise ValueError(f"Unsupported data type: {type(data)}")

            if em:
                # copy the previous values into this new value, `vars` ignores
                # property methods
                for n, v in vars(em).items():
                    setattr(self, n, v)

    def _get_path(self, basedir: str) -> str:
        """Internal method. Get the save path for this email, this should be a
        directory that all the parts can be saved into

        :param basedir: string, the base directory that will be used to
            generate a full path
        :returns: string, the full path to a directory this email can be saved
            into
        """
        stamp = self.datestamp("%Y-%m-%d %H%M%S")
        subject = self.get_subject("(no subject)")

        s = f"{stamp} - {subject}"

        # remove path delims from the subject
        s = re.sub(r"[\\/]+", " ", s)

        return Dirpath(
            basedir,
            f"{self.from_domain}",
            f"{self.from_address}/{s}",
        ).sanitize(maxpath=220)

    def _get_part_path(
        self,
        basedir: str,
        part: message.Message,
        index: int,
    ) -> str:
        """Internal method. Get the save path for this part

        :param basedir: string, the base directory this will use to generate a
            full path
        :returns: string, the full path to a file that this part could be
            saved to
        """
        if filename := part.get_filename():
            fileroot, ext = os.path.splitext(filename)

        else:
            content_type = part.get_content_type()
            fileroot = f"body {index}"
            ext = mimetypes.guess_extension(content_type, strict=False)
            if not ext:
                ext = ".txt"

        return Filepath(basedir, name=fileroot, ext=ext).sanitize()

    def save(self, basedir: str, save_original: bool = False) -> list[str]:
        """Save this email into basedir

        this will generate a base email path in the format:

            basedir/<FROM_DOMAIN>/<FROM_ADDR>/<DATE> - <SUBJECT>

        Then it will use this base email path to save all the headers, bodies,
        and attachments of the email

        :param basedir: string, path to save the email into
        :param save_original: bool, True if you would also like to save the
            full original email in original.eml. This defaults to False
            because it effectively doubles the size of the saved email so it
            should only be True if you really want to save the original
            eml: https://www.loc.gov/preservation/digital/formats/fdd/fdd000388.shtml
        :returns: list, all the paths the email saved
        """
        ret = []

        email_dir = self._get_path(basedir)
        email_dir.touch()
        ret.append(email_dir)

        if save_original:
            p = Filepath(email_dir, "original.eml")
            p.write_bytes(bytes(self))
            ret.append(p)

        for index, p in enumerate(self.walk_content(), 1):
            f = self._get_part_path(email_dir, p, index)
            data = p.get_payload(decode=True)
            if isinstance(data, bytes):
                f.write_bytes(data)

            else:
                f.write_text(data)

            ret.append(f)

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

