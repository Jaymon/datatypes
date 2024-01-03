# -*- coding: utf-8 -*-
import re
import os
import mimetypes
import time
from collections import defaultdict
import email.utils
from email.parser import Parser
from email.header import decode_header

from .compat import *
from .config.environ import environ
from .string import String, ByteString
from .datetime import Datetime
from .path import Filepath, Dirpath


class EmailPart(object):
    """Represents one part of a multipart email

    this class probably isn't useful outside of the Email class in this module
    """
    def __init__(self, email, content_type, contents, encoding, encodings=None, errors="", filename="", index=1):
        '''
        :param email: Email, the full email instance
        :param content_type: str, the mimetype of the part
        :param contents: str, the part's contents/body
        :param encoding: str, the content encoding
        :param encodings: list[str], the fallback encodings if encoding fails
        :param errors: str, how to handle encoding errors
        :param filename: str, filename for this attachment, if not provided this
            part will be considered a body instead of an attachment
        :param index: int, the part index/num of this email
        '''
        self.email = email
        self.content_type = content_type
        self.filename = filename
        self.encoding = encoding
        self.index = index

        if self.filename:
            # don't mess with the contents since this will be treated like a
            # binary file
            self.contents = contents

        else:
            try:
                self.contents = String(contents, encoding, errors)

            except LookupError as e:
                success = False
                if not encodings:
                    encodings = []

                try:
                    for enc in encodings:
                        self.contents = String(
                            contents,
                            enc,
                            errors=errors,
                        )
                        self.encoding = enc
                        success = True
                        break

                except Exception:
                    pass

                if not success:
                    raise UnicodeError(
                        encoding=encoding,
                        reason=" ".join([
                            f"Unable to decode with {encoding} encoding",
                            "even using alternate encodings",
                        ]),
                        object=contents
                    ) from e

    def path(self, basedir):
        """Get the save path for this part

        :param basedir: string, the base directory this will use to generate a
            full path
        :returns: string, the full path to a file that this part could be saved
            to
        """
        if self.filename:
            fileroot, ext = os.path.splitext(self.filename)

        else:
            content_type = self.content_type
            #fileroot = self.email.subject
            fileroot = f"body {self.index}"
            if content_type.endswith("plain"):
                ext = ".txt"

            else:
                ext = mimetypes.guess_extension(self.content_type, False)
                if not ext:
                    ext = ".txt"

        return Filepath(basedir, name=fileroot, ext=ext).sanitize()

    def save(self, basedir):
        '''Method to save the contents of an attachment to a file
        arguments:

        :param basedir: string, directory path where file is to be saved
        :returns: Path, the written filepath saved in basedir
        '''
        if not self.contents: return

        p = self.path(basedir)
        if self.filename:
            p.write_bytes(self.contents)

        else:
            p.write_text(self.contents)

        return p

    def is_attachment(self):
        """True if this is an attachment, False if it is a body"""
        return bool(self.filename)

    def is_body(self):
        """True if this is a body, False if it is an attachment"""
        return not self.is_attachment()


class Email(object):
    """Allow programmatic access to a raw email

    This was ripped out of popbak in December 2021 and plopped here

    The original email parsing portion of the code was based on code that I got
    from Larry Bates here:
        http://mail.python.org/pipermail/python-list/2004-June/265634.html
    """
    part_class = EmailPart
    """Each body or attachment in the email will be represented by this class"""

    @property
    def raw(self):
        return String(self.msg)

    @property
    def headers(self):
        # TODO -- convert the tuples to a dict?
        for name, value in self.msg.items():
            yield String(name), String(value)

    @property
    def subject(self):
        ret = self.msg.get('Subject', "")
        # https://stackoverflow.com/a/7331577/5006
        ds = decode_header(ret)
        if ds:
            ret, encoding = ds[0]
            ret = String(ret, encoding)

        if not ret:
            ret = "(no subject)"
        return ret

    @property
    def recipient_addrs(self):
        """return all the recipient email addresses

        https://docs.python.org/3/library/email.util.html#email.utils.getaddresses

        :returns: list, the list of recipients, this includes to, cc, bcc, etc.
        """
        tos = self.msg.get_all('to', [])
        ccs = self.msg.get_all('cc', [])
        bccs = self.msg.get_all('bcc', [])
        resent_tos = self.msg.get_all('resent-to', [])
        resent_ccs = self.msg.get_all('resent-cc', [])
        recipient_addrs = email.utils.getaddresses(
            tos + bccs + ccs + resent_tos + resent_ccs
        )
        return [String(a[1]) for a in recipient_addrs if a[1]]

    @property
    def to_addrs(self):
        """Only to addresses, ignore cc"""
        to_addrs = email.utils.getaddresses(self.msg.get_all('To', []))
        to_addrs = [String(a[1]) for a in to_addrs]
        return to_addrs

    @property
    def from_addr(self):
        """Get just the email address this email is from"""
        from_addr = ""
        from_addrs = email.utils.getaddresses(self.msg.get_all('From', []))
        return String(from_addrs[0][1]) if from_addrs else ""

    @property
    def from_domain(self):
        """Get the from email address domain (eg, the example.com of a
        foo@example.com email address)"""
        from_addr = self.from_addr
        return from_addr.rsplit("@", maxsplit=1)[-1]

    @property
    def date(self):
        """Get the string datestamp from the email"""
        ret = String(self.msg.get('Date', ""))
        return ret

    @property
    def datetime(self):
        """Convert .date into a datetime instance

        :returns: Datetime|None, if the date header exists this will return
            a datetime instance with the date the email was sent, if no date
            header is found then this will return None
        """
        d = self.date
        if d:
            # https://docs.python.org/3/library/email.util.html#email.utils.parsedate_tz
            t = email.utils.parsedate_tz(d)
            stamp = time.mktime(t[0:9])

            tz_offset = t[9]
            if tz_offset:
                stamp -= tz_offset

            return Datetime(stamp)

    @property
    def plain(self):
        """Return the plain text body of this email"""
        ret = self.parts["text/plain"]
        return ret[0].contents

    @property
    def html(self):
        """Return the html body of this email, if it exists"""
        ret = self.parts.get("text/html", [])
        ret = ret[0].contents if ret else ""
        return ret

    def __init__(self, contents, encodings=None, errors=""):
        """Encapsulate a pop email message

        :param contents: str, an original full email with all headers and parts
        :param encodings: list[str], the fallback encodings if the header
            defined encoding fails, this defaults to a list of the most common
            email encodings, the first encoding that succeeds will be used
        :param errors: str, how to handle encoding errors. Passing in "ignore"
            will make the email parser ignore encoding errors. See String for
            how errors is used and what the default is and how to change the
            default
        """
        self.contents = contents
        self.parts = defaultdict(list)

        if not encodings:
            encodings = ["UTF-8", "ISO-8859-1", "us-ascii"]

        self.msg = Parser().parsestr(String(contents))
        if self.msg.is_multipart():
            index = 0
            for part in self.msg.walk():
                # multipart/* are just containers
                if part.is_multipart():
                    continue

                # NOTE -- I'm not sure the lower is needed here, but just in
                # case
                content_type = part.get_content_type().lower()
                encoding = part.get_content_charset()
                filename = part.get_filename()
                part_contents = part.get_payload(decode=True)
                index += 1

                self.parts[content_type].append(self.part_class(
                    email=self,
                    content_type=content_type,
                    contents=part_contents,
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
            part_contents = self.msg.get_payload(decode=1)
            self.parts[content_type].append(self.part_class(
                email=self,
                content_type=content_type,
                contents=part_contents,
                encoding=encoding
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

        s = f"{stamp} - {self.subject}"

        # remove path delims from the subject
        s = re.sub(r"[\\/]+", " ", s)
        #s = re.sub(r"\s*[\\/*<>]+\s*", " ", s)
        #s = re.sub(r"[:?\"\'|^]", "", s)

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

    def has_attachments(self):
        """Does this email have attachments? Returns True or False"""
        for a in self.attachments():
            return True
        return False

    def has_attachment(self):
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
            p.write_bytes(ByteString(self.contents))
            ret.append(p)

        ret.append(email_dir)
        for ps in self.parts.values():
            for p in ps:
                rp = p.save(email_dir)
                if rp:
                    ret.append(rp)

        p = Filepath(email_dir, "headers.txt")
        with p.open_text("w+") as f:
            f.write("From:\n\t- {}\n".format(self.from_addr))
            f.write("Recipients:\n\t- {}\n".format(
                "\n\t- ".join(self.recipient_addrs)
            ))
            f.write("Subject: {}\n".format(self.subject))
            f.write("Date: {}\n\n".format(self.datestamp()))

            for name, val in self.headers:
                f.write("{}: {}\n".format(name, val))
        ret.append(p)

        return ret

