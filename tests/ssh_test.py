import os
import unittest

try:
    from datatypes.ssh import InfraSSH as SSH
except ImportError:
    SSH = None

from . import IsolatedAsyncioTestCase as TestCase


@TestCase.skipUnless(
    SSH is not None
    and "DATATYPES_SSH_TEST_HOST" in os.environ
    and "DATATYPES_SSH_TEST_USERNAME" in os.environ,
    "SSH Server environment variables not set",
)
class SSHTest(TestCase):
    def create_ssh_client(self):
        # matches the test ssh server values
        return SSH(
            host=os.environ["DATATYPES_SSH_TEST_HOST"],
            username=os.environ["DATATYPES_SSH_TEST_USERNAME"],
        )

    async def test_mkdir(self):
        client = self.create_ssh_client()
        async with client:
            # clear the directory
            await client.check_call(["rm", "-rf", "~/test_mkdir"])

            # create folders using different flags
            path = "~/test_mkdir/foo"
            await client.mkdir(path, parents=True)
            user = await client.check_output(
                ["stat", "-c", "%U", path],
                text=True,
            )
            group = await client.check_output(
                ["stat", "-c", "%G", path],
                text=True,
            )
            self.assertTrue(client.username == user.strip() == group.strip())

            path = "~/test_mkdir/bar"
            await client.mkdir(
                path,
                sudo=True,
                parents=True,
                user=client.username,
                group=client.username,
            )
            user = await client.check_output(
                ["stat", "-c", "%U", path],
                text=True,
            )
            group = await client.check_output(
                ["stat", "-c", "%G", path],
                text=True,
            )
            self.assertTrue(client.username == user.strip() == group.strip())

    async def test_check_output(self):
        client = self.create_ssh_client()
        #client.set_debug(True)
        async with client:
            # subprocess.check_output(...) # bytes
            s = await client.check_output(["echo", "hello"])
            self.assertTrue(isinstance(s, bytes))

            # subprocess.check_output(..., text=True) # str
            s = await client.check_output(["echo", "hello"], text=True)
            self.assertTrue(isinstance(s, str))

            # subprocess.check_output(..., encoding="UTF-8") # str
            s = await client.check_output(["echo", "hello"], encoding="UTF-8")
            self.assertTrue(isinstance(s, str))

            # subprocess.check_output(..., encoding="UTF-8", text=False) # str
            s = await client.check_output(
                ["echo", "hello"],
                encoding="UTF-8",
                text=False,
            )
            self.assertTrue(isinstance(s, str))

    async def test_has_package(self):
        client = self.create_ssh_client()
        async with client:
            package_name = "curl"

            await client.run(
                ["apt-get", "remove", "-y", package_name],
                sudo=True,
            )
            self.assertFalse(await client.has_package(package_name))

            await client.run(
                ["apt-get", "install", "-y", package_name],
                sudo=True,
            )
            self.assertTrue(await client.has_package(package_name))

    async def test_context(self):
        client = self.create_ssh_client()

        with client.options(foo=1):
            self.assertEqual(1, client.context_kwargs["foo"])

            async with client(bar=1, foo=2):
                self.assertEqual(2, client.context_kwargs["foo"])
                self.assertEqual(1, client.context_kwargs["bar"])

            self.assertFalse("bar" in client.context_kwargs)

        self.assertFalse("foo" in client.context_kwargs)

    async def test_runscript(self):
        client = self.create_ssh_client()

        async with client:
            r = await client.runscript("echo \"hello world\"")
            self.assertEqual("hello world", r.stdout.strip())

    async def test_env(self):
        client = self.create_ssh_client()
        environ = {
            "FOO": "1 2",
            "CHE": "3",
            "BAR": "$FOO $CHE 4",
        }

        async with client:
            r = await client.check_output(
                "pwd && echo $BAR",
                text=True,
                cwd="/etc",
                env=environ,
            )
            self.assertEqual("/etc\n1 2 3 4", r.rstrip())

            r = await client.check_output(
                "echo $BAR",
                text=True,
                env=environ,
            )
            self.assertEqual("1 2 3 4", r.rstrip())

            r = await client.check_output(
                #"echo $FOO",
                "echo $BAR",
                #"env",
                sudo=True,
                text=True,
                env=environ,
            )
            self.assertEqual("1 2 3 4", r.rstrip())

