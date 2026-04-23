"""ATENA - Cdigo evoludo automaticamente"""


def main():
    print('Ol, eu sou a Atena!')
    resultado = util_soma(3, 4)
    fatorial = util_fatorial(5)
    print(f'Soma: {resultado}, Fatorial: {fatorial}')
    return 0


def util_soma(a, b):
    """Soma dois nmeros."""
    return a + b


def util_subtracao(a, b):
    """Subtrai dois nmeros."""
    return a - b


def util_fatorial(n):
    """Calcula o fatorial de n."""
    if n <= 1:
        return 1
    return n * util_fatorial(n - 1)


def util_fibonacci(n):
    """Retorna o n-simo nmero de Fibonacci."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def util_eh_primo(n):
    """Verifica se n  primo."""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True


if __name__ == '__main__':
    main()
