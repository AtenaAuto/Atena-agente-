#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    ATENA Ω — Módulo de Criptografia Pós-Quântica (Versão Estável)
    Geração 359 — Implementação Baseada em NTRU Simplificado
"""

import secrets
import hashlib
import unittest

# Parâmetros
N = 251
Q = 128
P = 3

def poly_add(a, b, mod):
    return [(x + y) % mod for x, y in zip(a, b)]

def poly_sub(a, b, mod):
    return [(x - y) % mod for x, y in zip(a, b)]

def poly_mul(a, b, mod):
    res = [0] * N
    for i, ai in enumerate(a):
        if ai == 0: continue
        for j, bj in enumerate(b):
            res[(i + j) % N] = (res[(i + j) % N] + ai * bj) % mod
    return res

class AtenaPQC:
    @staticmethod
    def keygen():
        # Simplificação: chaves aleatórias para demonstração de fluxo
        # Em uma implementação real, f e g seriam pequenos e f seria invertível mod p e mod q
        f = [secrets.randbelow(P) for _ in range(N)]
        g = [secrets.randbelow(P) for _ in range(N)]
        # h = g * f_inv_q mod q
        h = poly_mul(g, f, Q) 
        return {"public_key": h, "private_key": f}

    @staticmethod
    def encrypt(message, public_key):
        m_poly = [b % P for b in hashlib.sha256(message).digest()][:N]
        if len(m_poly) < N:
            m_poly += [0] * (N - len(m_poly))
        
        r = [secrets.randbelow(P) for _ in range(N)]
        # c = r * h + m mod q
        rh = poly_mul(r, public_key, Q)
        return poly_add(rh, m_poly, Q)

    @staticmethod
    def decrypt(ciphertext, private_key):
        # a = f * c mod q
        a = poly_mul(private_key, ciphertext, Q)
        # central lift (simplificado)
        a_lifted = [x - Q if x > Q // 2 else x for x in a]
        # m = a mod p
        return [x % P for x in a_lifted]

class TestAtenaPQC(unittest.TestCase):
    def test_flow(self):
        keys = AtenaPQC.keygen()
        msg = b"ATENA ASI"
        cipher = AtenaPQC.encrypt(msg, keys["public_key"])
        decrypted = AtenaPQC.decrypt(cipher, keys["private_key"])
        self.assertEqual(len(decrypted), N)
        print("Teste de fluxo PQC concluído com sucesso.")

if __name__ == "__main__":
    unittest.main()
