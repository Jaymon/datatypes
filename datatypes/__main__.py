# -*- coding: utf-8 -*-
import sys
import argparse
# this is supposed to be removed in py3.12 but setuptools still uses it
# https://github.com/pypa/setuptools/blob/main/setuptools/__init__.py
import distutils.core
import re

from datatypes import logging
from datatypes import __version__
from datatypes.path import Dirpath
from datatypes.reflection import ReflectPath
from datatypes.config import Config
from datatypes.url import Url


logging.quick_config()
logger = logging.getLogger(__name__)


class Pyproject(object):

    name = "pyproject"

    description = " ".join([
        "Build a pyproject.toml file for the project in the given directory",
    ])

    @classmethod
    def handle(cls, args):

        dp = Dirpath.cwd()

        if dp.has_file("pyproject.toml"):
#             raise ValueError(
#                 "Cannot run this in a project that already has pyproject.toml"
#             )

            toml = Config(dp.get_file("pyproject.toml"))
            #pout.v(toml.jsonable())
            #pout.v(toml["project"]["license"])
            pout.v(toml["project"]["classifiers"])
            #pout.v({k: dict(v) for k, v in dict(toml))


        pout.x()



        rdp = ReflectPath(dp)

        #toml = {}
        toml = Config(dp.get_file("pyproject.toml"))
        project = {}
        urls = {}
        dependencies = {}
        setuptools = {}
        packages = {}
        dynamic = {}
        packagedata = {}
        entries = {}

        project["requires-python"] = ">=3.10"

        toml["build-system"] = {
            "requires": ["setuptools>=62.3.0"],
            "build-backend": "setuptools.build_meta",
        }

        #packages["exclude"] = ["tests", "tests.*", "*_test*", "example*"]
        packages["exclude"] = ["tests.*", "example*"]

        if dp.has_file("setup.py"):
            # setup.py can contain these fields:
            # https://docs.python.org/3/distutils/apiref.html#module-distutils.core

            # https://stackoverflow.com/a/42100532
            setup = distutils.core.run_setup(dp.child_file("setup.py"))
            #pout.v(setup)
            #pout.v(setup.metadata)
            #pout.v(setup.metadata._METHOD_BASENAMES)

            md = setup.metadata
            if md.description:
                project["description"] = md.description

            # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#authors-maintainers
            if md.author:
                author = {}
                author["name"] = md.author

                if md.author_email:
                    author["email"] = md.author_email

                project["authors"] = [author]

            # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#keywords
            if md.keywords:
                project["keywords"] = md.keywords

            # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#classifiers
            if md.classifiers:
                project["classifiers"] = md.classifiers

            # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#urls
            if md.url:
                urls["Homepage"] = md.url
#                 if "git" in md.url:
#                     urls["Repository"] = md.url
# 
#                 else:
#                     urls["Homepage"] = md.url

            # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#dependencies-optional-dependencies
            if setup.install_requires:
                project["dependencies"] = setup.install_requires

            if setup.tests_require:
                dependencies["tests"] = setup.tests_require

            if setup.extras_require:
                for key, deps in setup.extras_require.items():
                    dependencies[key] = deps

        # find the project name and version
        name = version = ""
        for rm in rdp.reflect_modules(depth=1):
            if rm.module_name == "setup":
                continue

            try:
                version = rm.get("__version__", "")
                if version:
                    name = rm.module_name
                    #toml["project"]["version"] = version
                    project["name"] = name
                    packages["include"] = [f"{name}.*"]
                    project["dynamic"] = ["version"]
                    dynamic["version"] = f"{name}.__version__"

                    for d in rm.data_dirs():
                        relpath = d.relative_to(rm.path)
                        modpath = relpath.replace("/", ".")
                        # https://stackoverflow.com/a/73593532
                        packagedata[modpath] = ["**"]

                    # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#entry-points
                    for rsm in rm.reflect_submodules():
                        if rsm.module_name.endswith("__main__"):
                            entry_point = rsm.reflect_class("EntryPoint")
                            if entry_point:
                                # TODO -- handle_<ENTRY_POINT_NAME>
                                entries[rsm.module_name] = "EntryPoint.handle"

                    break

            except (ImportError, SyntaxError) as e:
                pass

        # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#readme
        if dp.has_file("README.md"):
            project["readme"] = "README.md"

        elif dp.has_file("README.rst"):
            project["readme"] = "README.rst"

        # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#license
        if dp.has_file("LICENSE.txt"):
            project["license"] = {"file": "LICENSE.txt"}

        elif dp.has_file("LICENSE"):
            project["license"] = {"file": "LICENSE"}

        if dp.has_file(".git", "config"):
            c = Config(dp.get_file(".git", "config"))
            for section in c.sections():
                if "url" in c[section]:
                    gurl = c[section]["url"]
                    if "github.com" in gurl:
                        gurl = gurl.replace(":", "/")
                        gurl = re.sub(r"\.git$", "", gurl)
                        url = Url(
                            gurl,
                            username="",
                            password="",
                            scheme="https"
                        )
                        urls["Repository"] = url

        toml["project"] = project
        toml["project.urls"] = urls
        toml["project.optional-dependencies"] = dependencies
        toml["tool.setuptools"] = setuptools
        toml["tool.setuptools.packages.find"] = packages
        toml["tools.setuptools.dynamic"] = dynamic
        toml["tools.setuptools.package-data"] = packagedata
        toml["project.entry-points"] = entries

        #pout.v(toml["project"]["classifiers"])
        #pout.v(toml)
        toml.write()


class EntryPoint(object):
    name = ""

    description = "Datatypes CLI"

    @classmethod
    def handle(cls):
        parser = argparse.ArgumentParser(description=cls.description)
        parser.add_argument(
            "--version", "-V",
            action='version',
            version=f"%(prog)s {__version__}"
        )

        subparsers = parser.add_subparsers(dest="command", help="a sub command")
        subparsers.required = True # https://bugs.python.org/issue9253#msg186387

        # $ pout inject
        subparser = subparsers.add_parser(
            Pyproject.name,
            #parents=[common_parser],
            help=Pyproject.description,
            description=Pyproject.description,
            conflict_handler="resolve",
        )
        subparser.set_defaults(subclass=Pyproject)

        args = parser.parse_args()
        return args.subclass.handle(args)


if __name__ == "__main__":
    sys.exit(EntryPoint.handle())

