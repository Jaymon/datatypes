# -*- coding: utf-8 -*-
import re
import os
import mimetypes
import time
from collections import defaultdict
import email.utils
from email.parser import Parser
from email.header import decode_header

from . import environ
from .compat import *
from .string import String, ByteString
from .datetime import Datetime
from .path import Filepath, Dirpath


class EmailPart(object):
    """Represents one part of a multipart email

    this class probably isn't useful outside of the Email class in this module
    """
    def __init__(self, email, content_type, contents, encoding, filename="", index=1):
        '''
        :param email: Email, the full email instance
        :param content_type: string, the mimetype of the part
        :param contents: string, the part's contents/body
        :param encoding: string, the content encoding
        :param filename: string, filename for this attachment, if not provided this
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
            self.contents = String(contents, encoding)

    def path(self, basedir):
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
        return bool(self.filename)

    def is_body(self):
        return not self.is_attachment()


class Email(object):
    """Allow programmatic access to a raw email

    This was ripped out of popbak in December 2021 and plopped here

    The original email parsing portion of the code was based on code that I got from Larry Bates here:
        http://mail.python.org/pipermail/python-list/2004-June/265634.html
    """
    part_class = EmailPart

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
    def subject_basename(self):
        stamp = self.datetime.strftime("%Y-%m-%d %H%M")
        return f"{stamp} - {self.subject}"

    def path(self, basedir):
        s = self.subject_basename
        s = re.sub(r"\s*[\\/*<>]+\s*", " ", s)
        s = re.sub(r"[:?\"\'|^]", "", s)

        return Dirpath(
            basedir,
            f"{self.from_domain}",
            f"{self.from_addr}/{s}",
        ).sanitize(maxpath=220)

    def paths(self, basedir):
        email_dir = self.path(basedir)
        paths = [email_dir]
        for ps in self.parts.values():
            for p in ps:
                paths.append(p.path(email_dir))
        return paths

    @property
    def recipient_addrs(self):
        """return all the recipient email addresses

        https://docs.python.org/3/library/email.util.html#email.utils.getaddresses

        :returns: list, the list of recipients
        """
        tos = self.msg.get_all('to', [])
        ccs = self.msg.get_all('cc', [])
        bccs = self.msg.get_all('bcc', [])
        resent_tos = self.msg.get_all('resent-to', [])
        resent_ccs = self.msg.get_all('resent-cc', [])
        recipient_addrs = email.utils.getaddresses(tos + bccs + ccs + resent_tos + resent_ccs)
        return [String(a[1]) for a in recipient_addrs if a[1]]

    @property
    def to_addrs(self):
        to_addrs = email.utils.getaddresses(self.msg.get_all('To', []))
        to_addrs = [String(a[1]) for a in to_addrs]
        return to_addrs

    @property
    def from_addr(self):
        from_addr = ""
        from_addrs = email.utils.getaddresses(self.msg.get_all('From', []))
        return String(from_addrs[0][1]) if from_addrs else ""

    @property
    def from_domain(self):
        from_addr = self.from_addr
        return from_addr.rsplit("@", maxsplit=1)[-1]

    @property
    def date(self):
        ret = String(self.msg.get('Date', ""))
        return ret

    @property
    def datetime(self):
        d = self.date
        # https://docs.python.org/3/library/email.util.html#email.utils.parsedate_tz
        t = email.utils.parsedate_tz(d)
        tz_offset = t[9]
        stamp = time.mktime(t[0:9])
        if tz_offset:
            stamp -= tz_offset
        return Datetime(stamp)

    @property
    def isodate(self):
        return self.datetime.isoformat()

    @property
    def plain(self):
        ret = self.parts["text/plain"]
        return ret[0].contents

    @property
    def html(self):
        ret = self.parts.get("text/html", [])
        ret = ret[0].contents if ret else ""
        return ret

    def __init__(self, contents):
        """Encapsulate a pop email message

        :param contents: str, an original full email with all headers and parts
        """
        self.contents = contents
        self.parts = defaultdict(list)

        self.msg = Parser().parsestr(String(contents))
        if self.msg.is_multipart():
            index = 0
            for part in self.msg.walk():
                # multipart/* are just containers
                mptype=part.get_content_maintype()
                if mptype == "multipart": continue

                # NOTE -- I'm not sure the lower is needed here, but just in case
                content_type = part.get_content_type().lower()
                encoding = part.get_content_charset()
                filename = part.get_filename()
                part_contents = part.get_payload(decode=1)
                index += 1

                self.parts[content_type].append(self.part_class(
                    email=self,
                    content_type=content_type,
                    contents=part_contents,
                    encoding=encoding,
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

    def bodies(self):
        for ps in self.parts.values():
            for b in ps:
                if b.is_body():
                    yield b

    def attachments(self):
        for ps in self.parts.values():
            for a in ps:
                if a.is_attachment():
                    yield a

    def has_attachments(self):
        for a in self.attachments():
            return True
        return False

    def has_attachment(self):
        return self.has_attachments()

    def save(self, basedir):
        ret = []
        email_dir = self.path(basedir)
        email_dir.touch()

        ret.append(email_dir)
        for ps in self.parts.values():
            for p in ps:
                rp = p.save(email_dir)
                if rp:
                    ret.append(rp)

        p = Filepath(email_dir, "headers.txt")
        ret.append(p)
        with p.open_text("w+") as f:
            f.write("From:\n\t- {}\n".format(self.from_addr))
            f.write("Recipients:\n\t- {}\n".format("\n\t- ".join(self.recipient_addrs)))
            f.write("Subject: {}\n".format(self.subject))
            f.write("Date: {}\n\n".format(self.isodate))

            for name, val in self.headers:
                f.write("{}: {}\n".format(name, val))

        return ret

