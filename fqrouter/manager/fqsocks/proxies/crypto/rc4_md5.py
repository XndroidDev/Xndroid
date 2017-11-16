from __future__ import absolute_import, division, print_function, \
    with_statement

import hashlib
import M2Crypto.EVP

__all__ = ['ciphers']


def create_cipher(alg, key, iv, op, key_as_bytes=0, d=None, salt=None,
                  i=1, padding=1):
    md5 = hashlib.md5()
    md5.update(key)
    md5.update(iv)
    rc4_key = md5.digest()

    return M2Crypto.EVP.Cipher(b'rc4', rc4_key, b'', op,
                               key_as_bytes=0, d='md5', salt=None, i=1,
                               padding=1)


ciphers = {
    b'rc4-md5': (16, 16, create_cipher),
    }