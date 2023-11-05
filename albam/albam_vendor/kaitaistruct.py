import itertools
import sys
import struct
from io import open, BytesIO, SEEK_CUR, SEEK_END  # noqa

PY2 = sys.version_info[0] == 2

# Kaitai Struct runtime version, in the format defined by PEP 440.
# Used by our setup.cfg to set the version number in
# packaging/distribution metadata.
# Also used in Python code generated by older ksc versions (0.7 through 0.9)
# to check that the imported runtime is compatible with the generated code.
# Since ksc 0.10, the compatibility check instead uses the API_VERSION constant,
# so that the version string does not need to be parsed at runtime
# (see https://github.com/kaitai-io/kaitai_struct/issues/804).
__version__ = '0.11.dev1'

# Kaitai Struct runtime API version, as a tuple of ints.
# Used in generated Python code (since ksc 0.10) to check that the imported
# runtime is compatible with the generated code.
API_VERSION = (0, 11)

# pylint: disable=invalid-name,missing-docstring,too-many-public-methods
# pylint: disable=useless-object-inheritance,super-with-arguments,consider-using-f-string


class KaitaiStruct(object):
    def __init__(self, stream):
        self._io = stream

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        self._io.close()

    @classmethod
    def from_file(cls, filename):
        f = open(filename, 'rb')
        try:
            return cls(KaitaiStream(f))
        except Exception:
            # close file descriptor, then reraise the exception
            f.close()
            raise

    @classmethod
    def from_bytes(cls, buf):
        return cls(KaitaiStream(BytesIO(buf)))

    @classmethod
    def from_io(cls, io):
        return cls(KaitaiStream(io))


class ReadWriteKaitaiStruct(KaitaiStruct):
    def _fetch_instances(self):
        raise NotImplementedError()

    def _write(self, io=None):
        self._write__seq(io)
        self._fetch_instances()
        self._io.write_back_child_streams()

    def _write__seq(self, io):
        if io is not None:
            self._io = io


class KaitaiStream(object):
    def __init__(self, io):
        self._io = io
        self.align_to_byte()
        self.bits_le = False
        self.bits_write_mode = False

        self.write_back_handler = None
        self.child_streams = []

        try:
            self._size = self.size()
        # IOError is for Python 2 (IOError also exists in Python 3, but it has
        # become just an alias for OSError).
        #
        # Although I haven't actually seen a bare ValueError raised in this case
        # in practice, chances are some implementation may be doing it (see
        # <https://docs.python.org/3/library/io.html#io.IOBase> for reference:
        # "Also, implementations may raise a ValueError (or
        # UnsupportedOperation) when operations they do not support are
        # called."). And I've seen ValueError raised at least in Python 2 when
        # calling read() on an unreadable stream.
        except (OSError, IOError, ValueError):
            # tell() or seek() failed - we have a non-seekable stream (which is
            # fine for reading, but writing will fail, see
            # _write_bytes_not_aligned())
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        try:
            if self.bits_write_mode:
                self.write_align_to_byte()
        finally:
            self._io.close()

    # region Stream positioning

    def is_eof(self):
        if not self.bits_write_mode and self.bits_left > 0:
            return False

        # NB: previously, we first tried if self._io.read(1) did in fact read 1
        # byte from the stream (and then seeked 1 byte back if so), but given
        # that is_eof() may be called from both read and write contexts, it's
        # more universal not to use read() at all. See also
        # <https://github.com/kaitai-io/kaitai_struct_python_runtime/issues/75>.
        return self._io.tell() >= self.size()

    def seek(self, n):
        if self.bits_write_mode:
            self.write_align_to_byte()
        else:
            self.align_to_byte()

        self._io.seek(n)

    def pos(self):
        return self._io.tell() + (1 if self.bits_write_mode and self.bits_left > 0 else 0)

    def size(self):
        # Python has no internal File object API function to get
        # current file / StringIO size, thus we use the following
        # trick.
        io = self._io
        # Remember our current position
        cur_pos = io.tell()
        # Seek to the end of the stream and remember the full length
        full_size = io.seek(0, SEEK_END)

        if full_size is None:
            # In Python 2, the seek() method of 'file' objects (created by the
            # built-in open() function) has no return value, so we have to call
            # tell() ourselves to get the new absolute position - see
            # <https://github.com/kaitai-io/kaitai_struct_python_runtime/issues/72>.
            #
            # In Python 3, seek() methods of all
            # <https://docs.python.org/3/library/io.html> streams return the new
            # position already, so this won't be needed once we drop support for
            # Python 2.
            full_size = io.tell()

        # Seek back to the current position
        io.seek(cur_pos)
        return full_size

    # endregion

    # region Structs for numeric types

    packer_s1 = struct.Struct('b')
    packer_s2be = struct.Struct('>h')
    packer_s4be = struct.Struct('>i')
    packer_s8be = struct.Struct('>q')
    packer_s2le = struct.Struct('<h')
    packer_s4le = struct.Struct('<i')
    packer_s8le = struct.Struct('<q')

    packer_u1 = struct.Struct('B')
    packer_u2be = struct.Struct('>H')
    packer_u4be = struct.Struct('>I')
    packer_u8be = struct.Struct('>Q')
    packer_u2le = struct.Struct('<H')
    packer_u4le = struct.Struct('<I')
    packer_u8le = struct.Struct('<Q')

    packer_f4be = struct.Struct('>f')
    packer_f8be = struct.Struct('>d')
    packer_f4le = struct.Struct('<f')
    packer_f8le = struct.Struct('<d')

    # endregion

    # region Reading

    # region Integer numbers

    # region Signed

    def read_s1(self):
        return KaitaiStream.packer_s1.unpack(self.read_bytes(1))[0]

    # region Big-endian

    def read_s2be(self):
        return KaitaiStream.packer_s2be.unpack(self.read_bytes(2))[0]

    def read_s4be(self):
        return KaitaiStream.packer_s4be.unpack(self.read_bytes(4))[0]

    def read_s8be(self):
        return KaitaiStream.packer_s8be.unpack(self.read_bytes(8))[0]

    # endregion

    # region Little-endian

    def read_s2le(self):
        return KaitaiStream.packer_s2le.unpack(self.read_bytes(2))[0]

    def read_s4le(self):
        return KaitaiStream.packer_s4le.unpack(self.read_bytes(4))[0]

    def read_s8le(self):
        return KaitaiStream.packer_s8le.unpack(self.read_bytes(8))[0]

    # endregion

    # endregion

    # region Unsigned

    def read_u1(self):
        return KaitaiStream.packer_u1.unpack(self.read_bytes(1))[0]

    # region Big-endian

    def read_u2be(self):
        return KaitaiStream.packer_u2be.unpack(self.read_bytes(2))[0]

    def read_u4be(self):
        return KaitaiStream.packer_u4be.unpack(self.read_bytes(4))[0]

    def read_u8be(self):
        return KaitaiStream.packer_u8be.unpack(self.read_bytes(8))[0]

    # endregion

    # region Little-endian

    def read_u2le(self):
        return KaitaiStream.packer_u2le.unpack(self.read_bytes(2))[0]

    def read_u4le(self):
        return KaitaiStream.packer_u4le.unpack(self.read_bytes(4))[0]

    def read_u8le(self):
        return KaitaiStream.packer_u8le.unpack(self.read_bytes(8))[0]

    # endregion

    # endregion

    # endregion

    # region Floating point numbers

    # region Big-endian

    def read_f4be(self):
        return KaitaiStream.packer_f4be.unpack(self.read_bytes(4))[0]

    def read_f8be(self):
        return KaitaiStream.packer_f8be.unpack(self.read_bytes(8))[0]

    # endregion

    # region Little-endian

    def read_f4le(self):
        return KaitaiStream.packer_f4le.unpack(self.read_bytes(4))[0]

    def read_f8le(self):
        return KaitaiStream.packer_f8le.unpack(self.read_bytes(8))[0]

    # endregion

    # endregion

    # region Unaligned bit values

    def align_to_byte(self):
        self.bits_left = 0
        self.bits = 0

    def read_bits_int_be(self, n):
        self.bits_write_mode = False

        res = 0

        bits_needed = n - self.bits_left
        self.bits_left = -bits_needed % 8

        if bits_needed > 0:
            # 1 bit  => 1 byte
            # 8 bits => 1 byte
            # 9 bits => 2 bytes
            bytes_needed = ((bits_needed - 1) // 8) + 1  # `ceil(bits_needed / 8)`
            buf = self._read_bytes_not_aligned(bytes_needed)
            if PY2:
                buf = bytearray(buf)
            for byte in buf:
                res = res << 8 | byte

            new_bits = res
            res = res >> self.bits_left | self.bits << bits_needed
            self.bits = new_bits  # will be masked at the end of the function
        else:
            res = self.bits >> -bits_needed  # shift unneeded bits out

        mask = (1 << self.bits_left) - 1  # `bits_left` is in range 0..7
        self.bits &= mask

        return res

    # Unused since Kaitai Struct Compiler v0.9+ - compatibility with
    # older versions.
    def read_bits_int(self, n):
        return self.read_bits_int_be(n)

    def read_bits_int_le(self, n):
        self.bits_write_mode = False

        res = 0
        bits_needed = n - self.bits_left

        if bits_needed > 0:
            # 1 bit  => 1 byte
            # 8 bits => 1 byte
            # 9 bits => 2 bytes
            bytes_needed = ((bits_needed - 1) // 8) + 1  # `ceil(bits_needed / 8)`
            buf = self._read_bytes_not_aligned(bytes_needed)
            if PY2:
                buf = bytearray(buf)
            for i, byte in enumerate(buf):
                res |= byte << (i * 8)

            new_bits = res >> bits_needed
            res = res << self.bits_left | self.bits
            self.bits = new_bits
        else:
            res = self.bits
            self.bits >>= n

        self.bits_left = -bits_needed % 8

        mask = (1 << n) - 1  # no problem with this in Python (arbitrary precision integers)
        res &= mask
        return res

    # endregion

    # region Byte arrays

    def read_bytes(self, n):
        self.align_to_byte()
        return self._read_bytes_not_aligned(n)

    def _read_bytes_not_aligned(self, n):
        if n < 0:
            raise ValueError(
                "requested invalid %d amount of bytes" %
                (n,)
            )

        is_satisfiable = True
        # When a large number of bytes is requested, try to check first
        # that there is indeed enough data left in the stream.
        # This avoids reading large amounts of data only to notice afterwards
        # that it's not long enough. For smaller amounts of data, it's faster to
        # first read the data unconditionally and check the length afterwards.
        if (
            n >= 8*1024*1024  # = 8 MiB
            # in Python 2, there is a common error ['file' object has no
            # attribute 'seekable'], so we need to make sure that seekable() exists
            and callable(getattr(self._io, 'seekable', None))
            and self._io.seekable()
        ):
            num_bytes_available = self.size() - self.pos()
            is_satisfiable = (n <= num_bytes_available)

        if is_satisfiable:
            r = self._io.read(n)
            num_bytes_available = len(r)
            is_satisfiable = (n <= num_bytes_available)

        if not is_satisfiable:
            # noinspection PyUnboundLocalVariable
            raise EOFError(
                "requested %d bytes, but only %d bytes available" %
                (n, num_bytes_available)
            )

        # noinspection PyUnboundLocalVariable
        return r

    def read_bytes_full(self):
        self.align_to_byte()
        return self._io.read()

    def read_bytes_term(self, term, include_term, consume_term, eos_error):
        self.align_to_byte()
        r = b''
        while True:
            c = self._io.read(1)
            if c == b'':
                if eos_error:
                    raise Exception(
                        "end of stream reached, but no terminator %d found" %
                        (term,)
                    )

                return r

            if ord(c) == term:
                if include_term:
                    r += c
                if not consume_term:
                    self._io.seek(-1, SEEK_CUR)
                return r

            r += c

    def ensure_fixed_contents(self, expected):
        actual = self._io.read(len(expected))
        if actual != expected:
            raise Exception(
                "unexpected fixed contents: got %r, was waiting for %r" %
                (actual, expected)
            )
        return actual

    @staticmethod
    def bytes_strip_right(data, pad_byte):
        return data.rstrip(KaitaiStream.byte_from_int(pad_byte))

    @staticmethod
    def bytes_terminate(data, term, include_term):
        new_data, term_byte, _ = data.partition(KaitaiStream.byte_from_int(term))
        if include_term:
            new_data += term_byte
        return new_data

    # endregion

    # endregion

    # region Writing

    def _ensure_bytes_left_to_write(self, n, pos):
        try:
            full_size = self._size
        except AttributeError:
            raise ValueError("writing to non-seekable streams is not supported")

        num_bytes_left = full_size - pos
        if n > num_bytes_left:
            raise EOFError(
                "[%d] requested to write %d bytes, but only %d bytes left in the stream" %
                (full_size, n, num_bytes_left)
            )

    # region Integer numbers

    # region Signed

    def write_s1(self, v):
        self.write_bytes(KaitaiStream.packer_s1.pack(v))

    # region Big-endian

    def write_s2be(self, v):
        self.write_bytes(KaitaiStream.packer_s2be.pack(v))

    def write_s4be(self, v):
        self.write_bytes(KaitaiStream.packer_s4be.pack(v))

    def write_s8be(self, v):
        self.write_bytes(KaitaiStream.packer_s8be.pack(v))

    # endregion

    # region Little-endian

    def write_s2le(self, v):
        self.write_bytes(KaitaiStream.packer_s2le.pack(v))

    def write_s4le(self, v):
        self.write_bytes(KaitaiStream.packer_s4le.pack(v))

    def write_s8le(self, v):
        self.write_bytes(KaitaiStream.packer_s8le.pack(v))

    # endregion

    # endregion

    # region Unsigned

    def write_u1(self, v):
        self.write_bytes(KaitaiStream.packer_u1.pack(v))

    # region Big-endian

    def write_u2be(self, v):
        self.write_bytes(KaitaiStream.packer_u2be.pack(v))

    def write_u4be(self, v):
        self.write_bytes(KaitaiStream.packer_u4be.pack(v))

    def write_u8be(self, v):
        self.write_bytes(KaitaiStream.packer_u8be.pack(v))

    # endregion

    # region Little-endian

    def write_u2le(self, v):
        self.write_bytes(KaitaiStream.packer_u2le.pack(v))

    def write_u4le(self, v):
        self.write_bytes(KaitaiStream.packer_u4le.pack(v))

    def write_u8le(self, v):
        self.write_bytes(KaitaiStream.packer_u8le.pack(v))

    # endregion

    # endregion

    # endregion

    # region Floating point numbers

    # region Big-endian

    def write_f4be(self, v):
        self.write_bytes(KaitaiStream.packer_f4be.pack(v))

    def write_f8be(self, v):
        self.write_bytes(KaitaiStream.packer_f8be.pack(v))

    # endregion

    # region Little-endian

    def write_f4le(self, v):
        self.write_bytes(KaitaiStream.packer_f4le.pack(v))

    def write_f8le(self, v):
        self.write_bytes(KaitaiStream.packer_f8le.pack(v))

    # endregion

    # endregion

    # region Unaligned bit values

    def write_align_to_byte(self):
        if self.bits_left > 0:
            b = self.bits
            if not self.bits_le:
                b <<= 8 - self.bits_left

            # We clear the `bits_left` and `bits` fields using align_to_byte()
            # before writing the byte in the stream so that it happens even in
            # case the write fails. The reason is that if the write fails, it
            # would likely be a permanent issue that's not going to resolve
            # itself when retrying the operation with the same stream state, and
            # since seek() calls write_align_to_byte() at the beginning too, you
            # wouldn't be even able to seek anywhere without getting the same
            # exception again. So the stream could be in a broken state,
            # throwing the same exception over and over again even though you've
            # already processed it and you'd like to move on. And the only way
            # to get rid of it would be to call align_to_byte() externally
            # (given how it's currently implemented), but that's really just a
            # coincidence - that's a method intended for reading (not writing)
            # and it should never be necessary to call it from the outside (it's
            # more like an internal method now).
            #
            # So it seems more reasonable to deliver the exception once and let
            # the user application process it, but otherwise clear the bit
            # buffer to make the stream ready for further operations and to
            # avoid repeatedly delivering an exception for one past failed
            # operation. The rationale behind this is that it's not really a
            # failure of the "align to byte" operation, but the writing of some
            # bits to the stream that was requested earlier.
            self.align_to_byte()
            self._write_bytes_not_aligned(KaitaiStream.byte_from_int(b))

    def write_bits_int_be(self, n, val):
        self.bits_le = False
        self.bits_write_mode = True

        mask = (1 << n) - 1  # no problem with this in Python (arbitrary precision integers)
        val &= mask

        bits_to_write = self.bits_left + n
        bytes_needed = ((bits_to_write - 1) // 8) + 1  # `ceil(bits_to_write / 8)`

        # Unlike self._io.tell(), pos() respects the `bits_left` field (it
        # returns the stream position as if it were already aligned on a byte
        # boundary), which ensures that we report the same numbers of bytes here
        # as read_bits_int_*() methods would.
        self._ensure_bytes_left_to_write(bytes_needed - (1 if self.bits_left > 0 else 0), self.pos())

        bytes_to_write = bits_to_write // 8
        self.bits_left = bits_to_write % 8

        if bytes_to_write > 0:
            buf = bytearray(bytes_to_write)

            mask = (1 << self.bits_left) - 1  # `bits_left` is in range 0..7
            new_bits = val & mask
            val = val >> self.bits_left | self.bits << (n - self.bits_left)
            self.bits = new_bits

            for i in range(bytes_to_write - 1, -1, -1):
                buf[i] = val & 0xff
                val >>= 8
            self._write_bytes_not_aligned(buf)
        else:
            self.bits = self.bits << n | val

    def write_bits_int_le(self, n, val):
        self.bits_le = True
        self.bits_write_mode = True

        bits_to_write = self.bits_left + n
        bytes_needed = ((bits_to_write - 1) // 8) + 1  # `ceil(bits_to_write / 8)`

        # Unlike self._io.tell(), pos() respects the `bits_left` field (it
        # returns the stream position as if it were already aligned on a byte
        # boundary), which ensures that we report the same numbers of bytes here
        # as read_bits_int_*() methods would.
        self._ensure_bytes_left_to_write(bytes_needed - (1 if self.bits_left > 0 else 0), self.pos())

        bytes_to_write = bits_to_write // 8
        old_bits_left = self.bits_left
        self.bits_left = bits_to_write % 8

        if bytes_to_write > 0:
            buf = bytearray(bytes_to_write)

            new_bits = val >> (n - self.bits_left)  # no problem with this in Python (arbitrary precision integers)
            val = val << old_bits_left | self.bits
            self.bits = new_bits

            for i in range(bytes_to_write):
                buf[i] = val & 0xff
                val >>= 8
            self._write_bytes_not_aligned(buf)
        else:
            self.bits |= val << old_bits_left

        mask = (1 << self.bits_left) - 1  # `bits_left` is in range 0..7
        self.bits &= mask

    # endregion

    # region Byte arrays

    def write_bytes(self, buf):
        self.write_align_to_byte()
        self._write_bytes_not_aligned(buf)

    def _write_bytes_not_aligned(self, buf):
        n = len(buf)
        self._ensure_bytes_left_to_write(n, self._io.tell())
        self._io.write(buf)

    def write_bytes_limit(self, buf, size, term, pad_byte):
        n = len(buf)
        self.write_bytes(buf)
        if n < size:
            self.write_u1(term)
            pad_len = size - n - 1
            for _ in range(pad_len):
                self.write_u1(pad_byte)
        elif n > size:
            raise ValueError("writing %d bytes, but %d bytes were given" % (size, n))

    # endregion

    # endregion

    # region Byte array processing

    @staticmethod
    def process_xor_one(data, key):
        if PY2:
            return bytes(bytearray(v ^ key for v in bytearray(data)))

        return bytes(v ^ key for v in data)

    @staticmethod
    def process_xor_many(data, key):
        if PY2:
            return bytes(bytearray(a ^ b for a, b in zip(bytearray(data), itertools.cycle(bytearray(key)))))

        return bytes(a ^ b for a, b in zip(data, itertools.cycle(key)))

    @staticmethod
    def process_rotate_left(data, amount, group_size):
        if group_size != 1:
            raise Exception(
                "unable to rotate group of %d bytes yet" %
                (group_size,)
            )

        anti_amount = -amount % (group_size * 8)

        r = bytearray(data)
        for i, byte in enumerate(r):
            r[i] = (byte << amount) & 0xff | (byte >> anti_amount)
        return bytes(r)

    # endregion

    # region Misc runtime operations

    @staticmethod
    def int_from_byte(v):
        return ord(v) if PY2 else v

    @staticmethod
    def byte_from_int(i):
        return chr(i) if PY2 else bytes((i,))

    @staticmethod
    def byte_array_index(data, i):
        return KaitaiStream.int_from_byte(data[i])

    @staticmethod
    def byte_array_min(b):
        return KaitaiStream.int_from_byte(min(b))

    @staticmethod
    def byte_array_max(b):
        return KaitaiStream.int_from_byte(max(b))

    @staticmethod
    def byte_array_index_of(data, b):
        return data.find(KaitaiStream.byte_from_int(b))

    @staticmethod
    def resolve_enum(enum_obj, value):
        """Resolves value using enum: if the value is not found in the map,
        we'll just use literal value per se. Works around problem with Python
        enums throwing an exception when encountering unknown value.
        """
        try:
            return enum_obj(value)
        except ValueError:
            return value

    # endregion

    def to_byte_array(self):
        pos = self.pos()
        self.seek(0)
        r = self.read_bytes_full()
        self.seek(pos)
        return r

    class WriteBackHandler(object):
        def __init__(self, pos, handler):
            self.pos = pos
            self.handler = handler

        def write_back(self, parent):
            parent.seek(self.pos)
            self.handler(parent)

    def add_child_stream(self, child):
        self.child_streams.append(child)

    def write_back_child_streams(self, parent=None):
        _pos = self.pos()
        for child in self.child_streams:
            child.write_back_child_streams(self)

        # NOTE: Python 2 doesn't have list.clear() so it can't be used, see
        # https://docs.python.org/3.11/library/stdtypes.html#mutable-sequence-types
        # ("New in version 3.3: clear() and copy() methods.")
        del self.child_streams[:]
        self.seek(_pos)
        if parent is not None:
            self._write_back(parent)

    def _write_back(self, parent):
        self.write_back_handler.write_back(parent)


class KaitaiStructError(Exception):
    """Common ancestor for all error originating from Kaitai Struct usage.
    Stores KSY source path, pointing to an element supposedly guilty of
    an error.
    """
    def __init__(self, msg, src_path):
        super(KaitaiStructError, self).__init__("%s: %s" % (src_path, msg))
        self.src_path = src_path


class UndecidedEndiannessError(KaitaiStructError):
    """Error that occurs when default endianness should be decided with
    switch, but nothing matches (although using endianness expression
    implies that there should be some positive result).
    """
    def __init__(self, src_path):
        super(UndecidedEndiannessError, self).__init__("unable to decide on endianness for a type", src_path)


class ValidationFailedError(KaitaiStructError):
    """Common ancestor for all validation failures. Stores pointer to
    KaitaiStream IO object which was involved in an error.
    """
    def __init__(self, msg, io, src_path):
        super(ValidationFailedError, self).__init__("at pos %d: validation failed: %s" % (io.pos(), msg), src_path)
        self.io = io


class ValidationNotEqualError(ValidationFailedError):
    """Signals validation failure: we required "actual" value to be equal to
    "expected", but it turned out that it's not.
    """
    def __init__(self, expected, actual, io, src_path):
        super(ValidationNotEqualError, self).__init__("not equal, expected %s, but got %s" % (repr(expected), repr(actual)), io, src_path)
        self.expected = expected
        self.actual = actual


class ValidationLessThanError(ValidationFailedError):
    """Signals validation failure: we required "actual" value to be
    greater than or equal to "min", but it turned out that it's not.
    """
    def __init__(self, min_bound, actual, io, src_path):
        super(ValidationLessThanError, self).__init__("not in range, min %s, but got %s" % (repr(min_bound), repr(actual)), io, src_path)
        self.min = min_bound
        self.actual = actual


class ValidationGreaterThanError(ValidationFailedError):
    """Signals validation failure: we required "actual" value to be
    less than or equal to "max", but it turned out that it's not.
    """
    def __init__(self, max_bound, actual, io, src_path):
        super(ValidationGreaterThanError, self).__init__("not in range, max %s, but got %s" % (repr(max_bound), repr(actual)), io, src_path)
        self.max = max_bound
        self.actual = actual


class ValidationNotAnyOfError(ValidationFailedError):
    """Signals validation failure: we required "actual" value to be
    from the list, but it turned out that it's not.
    """
    def __init__(self, actual, io, src_path):
        super(ValidationNotAnyOfError, self).__init__("not any of the list, got %s" % (repr(actual)), io, src_path)
        self.actual = actual


class ValidationExprError(ValidationFailedError):
    """Signals validation failure: we required "actual" value to match
    the expression, but it turned out that it doesn't.
    """
    def __init__(self, actual, io, src_path):
        super(ValidationExprError, self).__init__("not matching the expression, got %s" % (repr(actual)), io, src_path)
        self.actual = actual


class ConsistencyError(Exception):
    def __init__(self, attr_id, actual, expected):
        super(ConsistencyError, self).__init__("Check failed: %s, expected: %s, actual: %s" % (attr_id, repr(expected), repr(actual)))
        self.id = attr_id
        self.actual = actual
        self.expected = expected
