"""Formatação de documentos, telefone e moeda."""

from decimal import Decimal, ROUND_HALF_UP
import re


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def formatar_cpf_cnpj(documento: str) -> str:
    digitos = somente_digitos(documento)
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) == 14:
        return (
            f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/"
            f"{digitos[8:12]}-{digitos[12:]}"
        )
    raise ValueError("CPF/CNPJ deve possuir 11 ou 14 dígitos.")


def formatar_telefone_whatsapp(telefone: str, ddi: str = "55") -> str:
    digitos = somente_digitos(telefone)
    if len(digitos) in {10, 11}:
        return f"{ddi}{digitos}"
    if digitos.startswith(ddi) and len(digitos) in {12, 13}:
        return digitos
    raise ValueError("Telefone inválido.")


def formatar_moeda(valor: Decimal) -> str:
    quantizado = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    inteiro, centavos = f"{quantizado:.2f}".split(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    milhares = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {milhares},{centavos}"
