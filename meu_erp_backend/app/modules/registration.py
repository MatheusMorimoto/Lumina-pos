"""Cadastro PF/PJ usando Supabase Auth e a função transacional do banco."""
from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from supabase import Client

from app.core.database import (
    get_authenticated_client,
    get_supabase_admin_client,
    get_supabase_anon_client,
    unwrap_response,
)
from app.shared.exceptions import ApplicationError, ConflictError


class UpstreamError(ApplicationError):
    status_code = 502
    code = "supabase_error"


class PersonType(StrEnum):
    COMPANY = "company"
    INDIVIDUAL = "individual"


class TaxRegime(StrEnum):
    MEI = "mei"
    SIMPLES_NACIONAL = "simples_nacional"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"
    PESSOA_FISICA = "pessoa_fisica"
    NAO_INFORMADO = "nao_informado"


def digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def valid_cpf(value: str) -> bool:
    value = digits(value)
    if len(value) != 11 or len(set(value)) == 1:
        return False
    numbers = [int(char) for char in value]
    for size in (9, 10):
        total = sum(numbers[index] * (size + 1 - index) for index in range(size))
        check = 11 - total % 11
        if check >= 10:
            check = 0
        if numbers[size] != check:
            return False
    return True


def valid_cnpj(value: str) -> bool:
    value = digits(value)
    if len(value) != 14 or len(set(value)) == 1:
        return False
    numbers = [int(char) for char in value]
    for size, weights in (
        (12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
        (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
    ):
        remainder = sum(numbers[index] * weights[index] for index in range(size)) % 11
        check = 0 if remainder < 2 else 11 - remainder
        if numbers[size] != check:
            return False
    return True


class RegistrationIn(BaseModel):
    person_type: PersonType
    email: str
    password: str = Field(min_length=8, max_length=128)
    phone: str
    postal_code: str
    street: str = Field(min_length=2, max_length=200)
    address_number: str = Field(min_length=1, max_length=30)
    complement: str | None = Field(default=None, max_length=100)
    neighborhood: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    state: str

    cnpj: str | None = None
    legal_name: str | None = Field(default=None, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    state_registration: str | None = None
    municipal_registration: str | None = None
    company_size: str | None = None
    main_cnae_code: str | None = None
    main_cnae_description: str | None = None
    registration_status: str | None = None
    simples_option: bool | None = None
    mei_option: bool | None = None
    regime_source: str | None = None
    data_manually_corrected: bool = False
    manually_reviewed: bool = False

    cpf: str | None = None
    full_name: str | None = Field(default=None, max_length=200)
    birth_date: date | None = None
    identity_document: str | None = None
    tax_regime: TaxRegime = TaxRegime.NAO_INFORMADO

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido.")
        return value

    @field_validator("phone", "postal_code", "cpf", "cnpj")
    @classmethod
    def normalize_numbers(cls, value: str | None) -> str | None:
        return digits(value) if value is not None else None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not 10 <= len(value) <= 13:
            raise ValueError("Telefone inválido.")
        return value

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, value: str) -> str:
        if len(value) != 8:
            raise ValueError("CEP deve conter 8 dígitos.")
        return value

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", value):
            raise ValueError("UF deve conter exatamente duas letras.")
        return value

    @model_validator(mode="after")
    def validate_person(self) -> "RegistrationIn":
        if self.person_type == PersonType.COMPANY:
            if not self.cnpj or not valid_cnpj(self.cnpj):
                raise ValueError("CNPJ inválido.")
            if not self.legal_name or len(self.legal_name.strip()) < 2:
                raise ValueError("Razão social é obrigatória.")
            if self.tax_regime == TaxRegime.PESSOA_FISICA:
                raise ValueError("Regime tributário incompatível com pessoa jurídica.")
        else:
            if not self.cpf or not valid_cpf(self.cpf):
                raise ValueError("CPF inválido.")
            if not self.full_name or len(self.full_name.strip()) < 2:
                raise ValueError("Nome completo é obrigatório.")
            if self.birth_date and self.birth_date > date.today():
                raise ValueError("Data de nascimento não pode estar no futuro.")
            if self.tax_regime not in {TaxRegime.PESSOA_FISICA, TaxRegime.NAO_INFORMADO}:
                raise ValueError("Regime tributário incompatível com pessoa física.")
        return self

    def registration_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"email", "password"}, exclude_none=True)


class RegistrationService:
    def __init__(self, auth_client: Client | None = None) -> None:
        self.auth_client = auth_client or get_supabase_anon_client()

    def register(self, data: RegistrationIn) -> tuple[int, dict[str, Any]]:
        created_user_id: str | None = None
        try:
            response = self.auth_client.auth.sign_up(
                {"email": data.email, "password": data.password}
            )
            user = response.user
            if not user:
                raise UpstreamError("O Supabase não criou o usuário.")
            created_user_id = str(user.id)
            session = response.session
            if not session:
                return 202, {
                    "user_id": created_user_id,
                    "email_confirmation_required": True,
                    "registration_complete": False,
                    "message": "Confirme o e-mail para concluir o cadastro.",
                }

            client = get_authenticated_client(session.access_token)
            result = unwrap_response(
                client.rpc(
                    "complete_registration", {"payload": data.registration_payload()}
                ).execute()
            )
            if not result:
                raise UpstreamError("Não foi possível concluir o cadastro.")
            registration = result[0]
            return 201, {
                "access_token": session.access_token,
                "token_type": "bearer",
                **registration,
                "registration_complete": True,
            }
        except ApplicationError:
            if created_user_id:
                self._compensate(created_user_id)
            raise
        except Exception as exc:
            if created_user_id:
                self._compensate(created_user_id)
            message = str(exc).lower()
            if any(term in message for term in ("already", "duplicate", "registered")):
                raise ConflictError("E-mail ou documento já cadastrado.") from None
            raise UpstreamError("Falha na comunicação com o Supabase.") from exc

    @staticmethod
    def _compensate(user_id: str) -> None:
        try:
            get_supabase_admin_client().auth.admin.delete_user(user_id)
        except Exception:
            # A remoção é best effort; o usuário sem perfil permanece sem acesso pelas RLS.
            pass


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = None
    postal_code: str | None = None
    street: str | None = None
    address_number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None


class FiscalProfilePatch(BaseModel):
    tax_regime: TaxRegime
    regime_source: str | None = None
    manually_reviewed: bool = True


class ProductTaxProfileIn(BaseModel):
    ncm: str = Field(min_length=8, max_length=8)
    cest: str | None = Field(default=None, max_length=7)
    merchandise_origin: str = Field(min_length=1, max_length=2)
    cfop: str = Field(min_length=4, max_length=4)
    cst_csosn: str | None = Field(default=None, max_length=4)
    pis_cst: str | None = Field(default=None, max_length=3)
    cofins_cst: str | None = Field(default=None, max_length=3)
    icms_rate: float = Field(default=0, ge=0, le=100)
    pis_rate: float = Field(default=0, ge=0, le=100)
    cofins_rate: float = Field(default=0, ge=0, le=100)
    ipi_rate: float = Field(default=0, ge=0, le=100)
    fcp_rate: float = Field(default=0, ge=0, le=100)
    destination_state: str | None = Field(default=None, min_length=2, max_length=2)
    operation_type: Literal["sale", "purchase", "return", "transfer"] = "sale"
    valid_from: date = Field(default_factory=date.today)
    valid_until: date | None = None
    manually_reviewed: bool = False

