# Copyright 2017, Andreas Ziegler <andreas.ziegler@fau.de>
#
# This file is part of librarytrader.
#
# librarytrader is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# librarytrader is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with librarytrader.  If not, see <http://www.gnu.org/licenses/>.

import collections
import os

from elftools.elf.dynamic import DynamicSection
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

class Library:

    def __init__(self, filename, load_elffile=True):
        if not os.path.isabs(filename):
            raise ValueError("{} is no absolute path".format(filename))

        self.fullname = filename

        if load_elffile:
            self._fd = open(filename, 'rb')
            self._elffile = ELFFile(self._fd)
            self.elfheader = self._elffile.header

        self.exports = collections.OrderedDict()
        self.imports = collections.OrderedDict()

        self.needed_libs = collections.OrderedDict()
        self.all_imported_libs = collections.OrderedDict()
        self.rpaths = []
        self.runpaths = []
        self.soname = None

    def parse_symtab(self):
        ei_osabi = self.elfheader['e_ident']['EI_OSABI']

        for section in self._elffile.iter_sections():
            if isinstance(section, SymbolTableSection):
                if section.name == '.symtab':
                    continue
                for _, symbol in enumerate(section.iter_symbols()):
                    shndx = symbol['st_shndx']
                    symbol_type = symbol['st_info']['type']
                    symbol_bind = symbol['st_info']['bind']

                    if symbol_type == 'STT_FUNC':
                        pass
                    elif (ei_osabi == 'ELFOSABI_LINUX' or \
                          ei_osabi == 'ELFOSABI_SYSV') \
                            and symbol_type == 'STT_LOOS':
                        # TODO: generic check for use of LOOS/IFUNC. libc uses
                        # STT_IFUNC (which is the same value as STT_LOOS) to
                        # provide multiple, architecture-specific
                        # implementations of stuff like memcpy, strcpy etc.
                        pass
                    else:
                        continue

                    if symbol_bind == 'STB_LOCAL':
                        continue

                    if shndx == 'SHN_UNDEF':
                        self.imports[symbol.name] = None
                    elif self.elfheader['e_type'] != 'ET_EXEC':
                        self.exports[symbol.name] = None

    def parse_dynamic(self):
        for section in self._elffile.iter_sections():
            if not isinstance(section, DynamicSection):
                continue
            for tag in section.iter_tags():
                if tag.entry.d_tag == 'DT_NEEDED':
                    self.needed_libs[tag.needed] = None
                elif tag.entry.d_tag == 'DT_RPATH':
                    self.rpaths = [rpath.replace("$ORIGIN",
                                                 os.path.dirname(self.fullname))
                                   for rpath in tag.rpath.split(':')]
                elif tag.entry.d_tag == 'DT_RUNPATH':
                    self.runpaths = [rpath.replace("$ORIGIN",
                                                   os.path.dirname(self.fullname))
                                     for rpath in tag.runpath.split(':')]
                elif tag.entry.d_tag == 'DT_SONAME':
                    self.soname = tag.soname

    def parse_functions(self, release=False):
        self.parse_symtab()
        self.parse_dynamic()
        if release:
            self._release_elffile()

    def _release_elffile(self):
        del self._elffile
        self._fd.close()
        del self._fd

    def is_compatible(self, other):
        hdr = self.elfheader
        o_hdr = other.elfheader
        return hdr['e_ident']['EI_CLASS'] == o_hdr['e_ident']['EI_CLASS'] and \
            hdr['e_machine'] == o_hdr['e_machine']

    def summary(self):
        return '{}: {} imports, {} exports, {} needed libs, ' \
                   '{} rpaths, {} runpaths' \
                   .format(self.fullname, len(self.imports), len(self.exports),
                           len(self.needed_libs), len(self.rpaths),
                           len(self.runpaths))

    def __str__(self):
        return self.summary()
