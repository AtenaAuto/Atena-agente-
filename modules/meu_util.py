#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mdulo de utilidades bsicas com boas prticas.
"""

import logging
from typing import Union, Optional

# Configurao de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def saudacao(nome: Optional[str] = None) -> str:
    """
    Retorna uma saudao personalizada.

    Args:
        nome (str, opcional): Nome da pessoa a ser saudada. Se no fornecido,
                              usa uma saudao genrica.

    Returns:
        str: Mensagem de saudao.

    Example:
        >>> saudacao("Maria")
        'Ol, Maria! Bem-vindo(a) ao mdulo.'
        >>> saudacao()
        'Ol! Seja bem-vindo(a) ao mdulo.'
    """
    if nome:
        msg = f"Ol, {nome}! Bem-vindo(a) ao mdulo."
    else:
        msg = "Ol! Seja bem-vindo(a) ao mdulo."
    
    logger.info(f"Saudao gerada para: {nome or 'annimo'}")
    return msg


def soma(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    Calcula a soma de dois nmeros.

    Args:
        a (int, float): Primeiro nmero.
        b (int, float): Segundo nmero.

    Returns:
        int ou float: Resultado da soma.

    Raises:
        TypeError: Se algum dos argumentos no for numrico.

    Example:
        >>> soma(3, 5)
        8
        >>> soma(2.5, 1.5)
        4.0
    """
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError(f"Ambos os argumentos devem ser nmeros. Recebidos: {type(a)}, {type(b)}")
    
    resultado = a + b
    logger.debug(f"Soma: {a} + {b} = {resultado}")
    return resultado


# 
# Opo com classe (para projetos maiores)
# 

class Calculadora:
    """Classe utilitria para operaes matemticas bsicas."""

    @staticmethod
    def somar(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Soma dois nmeros."""
        return soma(a, b)

    @staticmethod
    def saudacao(nome: Optional[str] = None) -> str:
        """Gera uma saudao."""
        return saudacao(nome)


# 
# Exemplo de uso (executado apenas quando o script  rodado diretamente)
# 

if __name__ == "__main__":
    import doctest
    doctest.testmod()  # Verifica os exemplos das docstrings
    
    print(saudacao("Usurio"))
    print(f"3 + 5 = {soma(3, 5)}")
    
    # Usando a classe
    calc = Calculadora()
    print(calc.saudacao("Dev"))
    print(f"2.5 + 1.5 = {calc.somar(2.5, 1.5)}")
