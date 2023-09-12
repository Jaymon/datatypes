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
from datatypes.config import TOML
from datatypes.url import Url


logging.quick_config()
logger = logging.getLogger(__name__)


class SetupToPyproject(object):
    """Converts a setup.py file to pyproject.toml

    Example pyproject.toml file:

        https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#example

    This is the issue that got me to write this:

        https://github.com/pypa/pip/issues/8559

    pyproject spec:

        https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#specification


    """

    name = "setup-to-pyproject"

    description = " ".join([
        "Convert setup.py to pyproject.toml for the project in the given",
        "directory",
    ])

    @classmethod
    def handle(cls, args):

        dp = Dirpath.cwd()

        if dp.has_file("pyproject.toml"):
            raise ValueError(
                "Cannot run this in a project that already has pyproject.toml"
            )

        if not dp.has_file("setup.py"):
            raise ValueError(
                "Cannot run this in a project that does not have a setup.py"
            )

        # setup.py can contain these fields:
        # https://docs.python.org/3/distutils/apiref.html#module-distutils.core

        # https://stackoverflow.com/a/42100532
        setup = distutils.core.run_setup(dp.child_file("setup.py"))
        toml = TOML(dp.get_file("pyproject.toml"))
        rdp = ReflectPath(dp)
        md = setup.metadata

        #pout.v(md)

        project = {}
        urls = {}
        dependencies = {}
        setuptools = {}
        packages = {}
        # https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html#dynamic-metadata
        dynamic = {}
        packagedata = {}
        entries = {}

        build_system = {
            "requires": ["setuptools>=62.3.0"],
            "build-backend": "setuptools.build_meta",
        }

        project["requires-python"] = ">=3.10"
        packages["exclude"] = ["tests*", "example*"]

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

        # https://pypi.python.org/pypi?:action=list_classifiers
        # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#classifiers
        if md.classifiers:
            project["classifiers"] = md.classifiers

        # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#urls
        if md.url:
            urls["Homepage"] = md.url

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

            version = rm.get("__version__", "")
            if version:
                name = rm.module_name
                #toml["project"]["version"] = version
                project["name"] = name
                packages["include"] = [f"{name}*"]

                # https://packaging.python.org/en/latest/guides/single-sourcing-package-version/#single-sourcing-the-package-version
                project["dynamic"] = ["version"]
                dynamic["version"] = {
                    "attr": f"{name}.__version__"
                }

                # https://setuptools.pypa.io/en/latest/userguide/datafiles.html
                # https://setuptools.pypa.io/en/latest/userguide/datafiles.html#subdirectory-for-data-files
                for d in rm.data_dirs():
                    setuptools["include-package-data"] = True
                    packages["namespaces"] = True
                    relpath = d.relative_to(rm.path)
                    modpath = relpath.replace("/", ".")
                    # https://stackoverflow.com/a/73593532
                    packagedata[modpath] = ["**"]

                # https://packaging.python.org/en/latest/specifications/entry-points/#entry-points
                # https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#entry-points
                for rsm in rm.reflect_submodules():
                    if rsm.module_name.endswith("__main__"):
                        entries[rsm.module_name] = "<ADD ENTRY POINT>"

#                         entry_point = rsm.reflect_class("EntryPoint")
#                         if entry_point:
#                             # TODO -- handle_<ENTRY_POINT_NAME>
#                             entries[rsm.module_name] = "EntryPoint.handle"

                break

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

        if repository := rdp.remote_repository_url():
            urls["Repository"] = repository

        toml.add_section("project").update(project)
        toml.add_section("project.urls").update(urls)
        toml.add_section("project.optional-dependencies").update(dependencies)
        toml.add_section("project.entry-points").update(entries)

        toml.add_section("build-system").update(build_system)
        toml.add_section("tool.setuptools").update(setuptools)
        toml.add_section("tool.setuptools.packages.find").update(packages)
        toml.add_section("tool.setuptools.dynamic").update(dynamic)
        toml.add_section("tool.setuptools.package-data").update(packagedata)

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

        subparser = subparsers.add_parser(
            SetupToPyproject.name,
            #parents=[common_parser],
            help=SetupToPyproject.description,
            description=SetupToPyproject.description,
            conflict_handler="resolve",
        )
        subparser.set_defaults(subclass=SetupToPyproject)

        args = parser.parse_args()
        return args.subclass.handle(args)


if __name__ == "__main__":
    sys.exit(EntryPoint.handle())

