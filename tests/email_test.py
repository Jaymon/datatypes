import io

from datatypes.compat import *
from datatypes.email import (
    Email,
    EmailAddress,
    get_decoded_header,
)
from datatypes.string import ByteString

from . import TestCase, testdata


class EmailTest(TestCase):
    def get_email(self, fileroot, **kwargs):
        contents = testdata.get_contents(fileroot)
        return Email(contents, **kwargs)

    def test_parse_multipart(self):
        em = self.get_email("emoji-html-attachment")

        self.assertTrue(em.has_attachments())
        self.assertEqual(1, len(list(em.attachments())))
        self.assertEqual("foo@example.com", em.from_addr)

        emoji = b'\xf0\x9f\x98\x82\xf0\x9f\x98\x8e\xf0\x9f\x91\x8d'
        self.assertTrue(emoji in ByteString(em.plain))
        self.assertTrue(emoji in ByteString(em.html))

    def test_parse_simple(self):
        em = self.get_email("simple-text")

        self.assertFalse(em.has_attachments())
        self.assertEqual("", em.html)

        shrug = b'\xc2\xaf\\_(\xe3\x83\x84)_/\xc2\xaf'
        self.assertTrue(shrug in ByteString(em.plain))

    def test_parse_subject_multi_to(self):
        em = self.get_email("no-subject")
        self.assertEqual(2, len(em.to_addrs))
        self.assertTrue("" in em.subject)

    def test_parse_cc(self):
        em = self.get_email("cc")
        self.assertEqual("foo@example.com", em.from_addr)

    def test_bad_subject(self):
        em = self.get_email("bad-1")
        self.assertEqual(
            "PitchBook PE & VC News: Changing Course — PE Pivots Away from B2C Education, Toward B2B",
            em.subject
        )

    def test_bad_2(self):
        basedir = testdata.create_dir()
        em = self.get_email("bad-2")

        paths = em.save(basedir)
        email_dir = paths[0]
        self.assertEqual(5, email_dir.filecount())

    def test_original(self):
        """makes sure the original.txt file exists and isn't empty"""
        basedir = testdata.create_dir()
        em = self.get_email("bad-2")

        count = 0
        paths = em.save(basedir, save_original=True)
        for p in paths:
            if p.endswith("original.eml"):
                count = p.count()
        self.assertLess(0, count)

    def test_save(self):
        basedir = testdata.create_dir()
        em = self.get_email("emoji-html-attachment")
        paths = em.save(basedir)
        self.assertEqual(5, len(paths))

        em = self.get_email("cc")
        paths = em.save(basedir)
        self.assertEqual(3, len(paths))

        em = self.get_email("no-subject")
        paths = em.save(basedir)
        self.assertEqual(3, len(paths))

        em = self.get_email("simple-text")
        paths = em.save(basedir)
        self.assertEqual(3, len(paths))

    def test_subject_slashes(self):
        em = self.get_email("subject-slashes")
        tr = "".join([
            "/example.com/foo@example.com/2018-06-07 142121 - [Name] Error in foo Library Developer "
            "Devices 9B98F192-6530-2234976EB546 data Bundle 555B3437-8CF1-369E46E3AB15 ",
            "Bar Staging.app main.ext293"
        ])
        self.assertEqual(tr, em.path("/"))

    def test_subject_question_mark(self):
        em = self.get_email("subject-question-mark")
        tr = "".join([
            "/example.com/foo@example.com/2018-06-07 142121 - [Action Required] Database Version ",
            "Upgrade For Your Amazon Aurora PostgreSQL Database Instances ",
            "[AWS Account NNNNNNNN]",
        ])
        self.assertEqual(tr, em.path("/"))

    def test_subject_encoded(self):
        em = self.get_email("subject-encoded")
        self.assertEqual("You're #1 - Come check these drops out...\U0001F440", em.subject)

    def test_bad_content_type(self):
        """Make sure an email part with unknown-8bit encoding can be safely
        parsed if errors are set to ignore

        RFC 1428 defines the charset "UNKNOWN-8BIT" to refer to data for which
        the encoder does not know the charset.  The MIME encoded-word decoder
        should use the default charset for decoding this data.  Currently the
        decoder passes "unknown-8bit" down to the charset converter, which in
        turn treats the unrecognized charset as iso-8859-1.
        """
        em = self.get_email("bad-content-type", errors="ignore")
        p = em.parts["text/plain"][2]
        self.assertEqual("UTF-8", p.encoding)

    def test_no_date(self):
        """Gmail's welcome message in really old gmail accounts (mine dates
        to the first year of Gmail's existence) doesn't have a date"""
        em = self.get_email("no-date")
        self.assertIsNone(em.datetime)

        basedir = testdata.create_dir()
        paths = em.save(basedir)
        self.assertTrue(paths[0].basename.startswith("UNKNOWN"))

    def test_addresses(self):
        data = self.create_email_message(
            headers={
                "cc": [
                    self.get_email_address(),
                    self.get_email_address(),
                ],
                "bcc": self.get_email_address(),
            },
        )
        em = Email(bytes(data))
        addresses = em.addresses
        self.assertEqual(5, len(addresses))
        seen = set()
        for addr in addresses:
            self.assertTrue(addr not in seen)
            seen.add(addr)

    def test_references(self):
        msgids = [
            self.get_email_msgid(),
            self.get_email_msgid(),
            self.get_email_msgid(),
        ]
        data = self.create_email_message(
            prev_msgids=msgids,
        )

        em = Email(str(data))
        self.assertEqual(msgids, em.references)

    def test_msgid_no_header(self):
        data = self.create_email_message()
        del data["Message-ID"]
        em = Email(data)
        self.assertEqual(em.msgid, em.msgid)

    def test_to_address(self):
        to_addr = self.get_email_address()
        data = self.create_email_message(to_address=to_addr)

        del data["Delivered-To"]
        em = Email(data)
        self.assertEqual(to_addr, em.to_address)

        data["Delivered-To"] = to_addr
        em = Email(data)
        self.assertEqual(to_addr, em.to_address)

    def test_headers(self):
        data = self.create_email_message()
        em = Email(data)
        self.assertIsNotNone(em.headers)

    def test_bytes_1(self):
        data = self.create_email_message()
        em = Email(bytes(data))
        self.assertTrue(isinstance(em.plain, str))

    def test_bytes_io(self):
        data = self.create_email_message()
        fp = self.create_file(bytes(data))
        with open(fp, "rb") as buffer:
            em = Email(buffer)
            self.assertTrue(isinstance(em.plain, str))

        buffer = io.BytesIO(bytes(data))
        em = Email(buffer)
        self.assertTrue(isinstance(em.plain, str))

    def test_str_io(self):
        data = self.create_email_message()
        fp = self.create_file(bytes(data))
        with open(fp, "r", encoding="UTF-8") as buffer:
            em = Email(buffer)
            self.assertTrue(isinstance(em.plain, str))

        buffer = io.StringIO(str(data))
        em = Email(buffer)
        self.assertTrue(isinstance(em.plain, str))

    def test_subject_bytes(self):
        words = self.get_unicode_words()
        em1 = Email(bytes(
            self.create_email_message(
                subject="foo " + words,
                data="foo bar",
            ),
        ))

        em2 = Email(bytes(em1))
        subject = em2.subject
        self.assertTrue(isinstance(subject, str))
        self.assertTrue("foo " in subject)
        self.assertTrue(words in subject)


class GetDecodedHeaderTest(TestCase):
    def test_1(self):
        h = get_decoded_header("foo bar")
        self.assertEqual("foo bar", h)

    def test_2(self):
        data = "pede. =?utf-8?q?=F0=A5=84=AB?="
        h = get_decoded_header(data)
        self.assertEqual("pede. \U0002512B", h)

    def test_3(self):
        data = "=?utf-8?q?=F0=A5=84=AB?="
        h = get_decoded_header(data)
        self.assertEqual("\U0002512B", h)


class EmailAddressTest(TestCase):
    def test_properties(self):
        em = EmailAddress("foo@bar.com")
        self.assertEqual("foo", em.username)
        self.assertEqual("bar.com", em.domain)
        self.assertEqual("", em.name)
        self.assertEqual("foo@bar.com", em)

        em = EmailAddress("Che Baz <foo@bar.com>")
        self.assertEqual("foo", em.username)
        self.assertEqual("bar.com", em.domain)
        self.assertEqual("Che Baz", em.name)
        self.assertEqual("foo@bar.com", em)

        em = EmailAddress(("Che Baz", "foo@bar.com"))
        self.assertEqual("foo", em.username)
        self.assertEqual("bar.com", em.domain)
        self.assertEqual("Che Baz", em.name)
        self.assertEqual("foo@bar.com", em)

    def test_encoding(self):
        name = self.get_unicode_name()
        em = EmailAddress((name, self.get_email_address()))
        em = EmailAddress(em.formataddr())
        self.assertEqual(name, em.name)

