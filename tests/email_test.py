# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.email import (
    Email,
)
from datatypes.string import ByteString

from . import TestCase, testdata


class EmailTest(TestCase):
    def get_email(self, fileroot, **kwargs):
        contents = testdata.get_contents(fileroot)
        return Email(contents, **kwargs)

#         body = testdata.get_contents(fileroot)
#         lines = body.splitlines(False)
#         contents = (b'+OK message follows', [ByteString(l) for l in lines], len(lines))
#         return EmailMsg(1, contents)

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
        self.assertTrue("(no subject)" in em.subject)

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

