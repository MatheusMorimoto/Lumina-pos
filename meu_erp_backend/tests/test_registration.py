"""Validação do contrato de cadastro PF/PJ sem depender do Supabase remoto."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.modules.registration import RegistrationIn, valid_cnpj, valid_cpf


def common() -> dict:
    return {
        "email": " USER@Example.COM ", "password": "senha-segura1",
        "password_confirmation": "senha-segura1",
        "phone": "(65) 99999-9999", "postal_code": "78000-000",
        "street": "Rua Principal", "address_number": "25",
        "neighborhood": "Centro", "city": "Cuiabá", "state": "mt",
    }


def test_cpf_valido_e_normalizado() -> None:
    data = RegistrationIn(
        **common(), person_type="individual", cpf="529.982.247-25",
        full_name="Pessoa Exemplo", birth_date="1990-05-10", tax_regime="pessoa_fisica",
    )
    assert data.cpf == "52998224725"
    assert data.email == "user@example.com"
    assert data.state == "MT"


def test_rejeita_cpf_invalido_e_repetido() -> None:
    assert not valid_cpf("111.111.111-11")
    with pytest.raises(ValidationError, match="CPF inválido"):
        RegistrationIn(
            **common(), person_type="individual", cpf="52998224724",
            full_name="Pessoa Exemplo", tax_regime="pessoa_fisica",
        )


def test_cnpj_valido_e_normalizado() -> None:
    data = RegistrationIn(
        **common(), person_type="company", cnpj="11.222.333/0001-81",
        legal_name="Empresa Exemplo LTDA", trade_name="Empresa Exemplo",
        legal_representative_name="Responsavel Exemplo",
        legal_representative_cpf="529.982.247-25", tax_regime="simples_nacional",
    )
    assert valid_cnpj(data.cnpj or "")
    assert data.cnpj == "11222333000181"


def test_rejeita_cnpj_com_tamanho_invalido() -> None:
    with pytest.raises(ValidationError, match="CNPJ inválido"):
        RegistrationIn(
            **common(), person_type="company", cnpj="123",
            legal_name="Empresa Exemplo LTDA", trade_name="Empresa Exemplo",
            legal_representative_name="Responsavel Exemplo",
            legal_representative_cpf="52998224725", tax_regime="simples_nacional",
        )


def test_rejeita_nascimento_futuro() -> None:
    with pytest.raises(ValidationError, match="futuro"):
        RegistrationIn(
            **common(), person_type="individual", cpf="52998224725",
            full_name="Pessoa Exemplo", birth_date=date.today() + timedelta(days=1),
            tax_regime="pessoa_fisica",
        )


def test_rotas_de_cadastro_e_fiscal_publicadas() -> None:
    paths = app.openapi()["paths"]
    assert "/api/auth/register" in paths
    assert "/api/account" in paths
    assert "/api/account/fiscal-profile" in paths
    assert "/api/products/{product_id}/tax-profile" in paths
    assert "/api/auth/password/recover" in paths
    assert "/api/auth/password/update" in paths


def test_aceita_contrato_aninhado_do_relatorio() -> None:
    data = RegistrationIn.model_validate({
        "person_type": "individual", "name": "Pessoa Exemplo",
        "cpf": "529.982.247-25", "birth_date": "1990-05-10",
        "email": "pessoa@example.com", "phone": "65999999999",
        "password": "SenhaSegura1", "password_confirmation": "SenhaSegura1",
        "address": {"postal_code": "78000000", "street": "Rua Principal",
                    "number": "25", "district": "Centro", "city": "Cuiaba",
                    "state": "MT"},
    })
    assert data.full_name == "Pessoa Exemplo"
    assert data.address_number == "25"
    assert "password" not in data.registration_payload()
    assert "password_confirmation" not in data.registration_payload()


def test_rejeita_confirmacao_de_senha_diferente() -> None:
    payload = common()
    payload["password_confirmation"] = "OutraSenha1"
    with pytest.raises(ValidationError, match="senhas nao coincidem"):
        RegistrationIn(
            **payload, person_type="individual", cpf="52998224725",
            full_name="Pessoa Exemplo", birth_date="1990-05-10",
        )


def test_conta_exige_token() -> None:
    response = TestClient(app).get("/api/account")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"
